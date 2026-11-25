"""Страница «заказы в реальном времени» для персонала (HTTP Basic, те же логин/пароль, что у админки).

Страница раз в 3 секунды запрашивает активные заказы и позволяет переключить статус вручную.
"""
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.metrics import ORDER_STATUS_CHANGES
from app.models import Order, OrderStatus
from app.routers.orders import get_order_or_404
from app.schemas.order import OrderOut, OrderStatusUpdate

security = HTTPBasic()


def require_staff(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    user_ok = secrets.compare_digest(
        credentials.username.encode(), settings.admin_username.encode()
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode(), settings.admin_password.encode()
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )


router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_staff)]
)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page() -> str:
    return DASHBOARD_HTML


@router.get("/api/orders", response_model=List[OrderOut], summary="Активные заказы")
async def active_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.status != OrderStatus.COMPLETED.value)
        .order_by(Order.id)
    )
    return result.scalars().all()


@router.patch(
    "/api/orders/{order_id}/status", response_model=OrderOut, summary="Сменить статус вручную"
)
async def set_status(
    body: OrderStatusUpdate,
    order_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    order = await get_order_or_404(db, order_id)
    order.status = body.status.value
    await db.commit()
    ORDER_STATUS_CHANGES.labels(status=body.status.value, source="dashboard").inc()
    return order


DASHBOARD_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Заказы онлайн</title>
<style>
  body { font-family: sans-serif; margin: 2rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
  th { background: #f3f3f3; }
  #updated { color: #666; }
</style>
</head>
<body>
<h1>Текущие заказы</h1>
<p id="updated">Загрузка...</p>
<table>
  <thead><tr><th>#</th><th>Состав</th><th>Сумма</th><th>Статус</th></tr></thead>
  <tbody id="rows"></tbody>
</table>
<script>
const STATUSES = ["принят", "готовится", "доставляется", "завершён"];

async function load() {
  // не перерисовываем таблицу, пока сотрудник выбирает статус
  if (document.activeElement && document.activeElement.tagName === "SELECT") return;
  const res = await fetch("/dashboard/api/orders");
  const info = document.getElementById("updated");
  if (!res.ok) { info.textContent = "Ошибка загрузки: " + res.status; return; }
  const orders = await res.json();
  const tbody = document.getElementById("rows");
  tbody.replaceChildren();
  for (const o of orders) {
    const tr = document.createElement("tr");
    const cells = [
      String(o.id),
      o.items.map(i => i.dish_name + " x" + i.quantity).join(", "),
      o.total.toFixed(2),
    ];
    for (const text of cells) {
      const td = document.createElement("td");
      td.textContent = text;  // textContent — защита от XSS через названия блюд
      tr.appendChild(td);
    }
    const tdStatus = document.createElement("td");
    const select = document.createElement("select");
    for (const s of STATUSES) {
      const opt = document.createElement("option");
      opt.value = s; opt.textContent = s;
      if (s === o.status) opt.selected = true;
      select.appendChild(opt);
    }
    select.addEventListener("change", async () => {
      await fetch("/dashboard/api/orders/" + o.id + "/status", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: select.value }),
      });
      select.blur();
      load();
    });
    tdStatus.appendChild(select);
    tr.appendChild(tdStatus);
    tbody.appendChild(tr);
  }
  info.textContent = "Обновлено: " + new Date().toLocaleTimeString();
}
load();
setInterval(load, 3000);
</script>
</body>
</html>
"""
