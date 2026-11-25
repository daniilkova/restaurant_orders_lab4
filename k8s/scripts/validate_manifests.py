"""Проверка Kubernetes-манифестов по JSON-схемам (строгий режим, как kubeconform -strict).

Встроенные ресурсы — схемы Kubernetes из пакета kubernetes-validate,
CRD (KEDA, CloudNativePG, Argo CD, ...) — схемы из каталога datreeio/CRDs-catalog.

    pip install kubernetes-validate jsonschema pyyaml
    python scripts/validate_manifests.py k8s/*.yaml k8s/keda/*.yaml argocd/*.yaml
    helm template restaurant helm/fastapi-platform | python scripts/validate_manifests.py -
"""
import argparse
import json
import os
import sys
import urllib.request

import jsonschema
import kubernetes_validate
import yaml
from kubernetes_validate.utils import InvalidSchemaError, SchemaNotFoundError, ValidationError

POD_KINDS = {"Pod": [], "Deployment": ["spec", "template"], "StatefulSet": ["spec", "template"],
             "DaemonSet": ["spec", "template"], "Job": ["spec", "template"],
             "CronJob": ["spec", "jobTemplate", "spec", "template"]}
ALLOWED_VOLUMES = {"configMap", "csi", "downwardAPI", "emptyDir", "ephemeral",
                   "persistentVolumeClaim", "projected", "secret", "name"}


def check_pss_restricted(doc: dict) -> list:
    """Проверки профиля Pod Security Standards «restricted» (как у admission-контроллера PSA)."""
    path = POD_KINDS.get(doc.get("kind"))
    if path is None:
        return []
    pod = doc
    for key in path:
        pod = pod.get(key, {})
    spec = pod.get("spec", {}) if doc["kind"] != "Pod" else doc.get("spec", {})
    psc = spec.get("securityContext") or {}
    problems = []
    for flag in ("hostNetwork", "hostPID", "hostIPC"):
        if spec.get(flag):
            problems.append(f"{flag}=true")
    for vol in spec.get("volumes") or []:
        bad = set(vol) - ALLOWED_VOLUMES
        if bad:
            problems.append(f"том {vol.get('name')}: тип {sorted(bad)} запрещён")
    containers = (spec.get("containers") or []) + (spec.get("initContainers") or [])
    for c in containers:
        csc = c.get("securityContext") or {}
        name = c.get("name")
        if csc.get("privileged"):
            problems.append(f"{name}: privileged")
        if csc.get("allowPrivilegeEscalation") is not False:
            problems.append(f"{name}: allowPrivilegeEscalation должен быть false")
        caps = csc.get("capabilities") or {}
        if "ALL" not in (caps.get("drop") or []):
            problems.append(f"{name}: capabilities.drop должен содержать ALL")
        if set(caps.get("add") or []) - {"NET_BIND_SERVICE"}:
            problems.append(f"{name}: запрещённые capabilities.add {caps.get('add')}")
        if not (csc.get("runAsNonRoot") or psc.get("runAsNonRoot")):
            problems.append(f"{name}: runAsNonRoot не задан")
        if csc.get("runAsUser", psc.get("runAsUser")) == 0:
            problems.append(f"{name}: runAsUser=0")
        seccomp = (csc.get("seccompProfile") or psc.get("seccompProfile") or {}).get("type")
        if seccomp not in ("RuntimeDefault", "Localhost"):
            problems.append(f"{name}: seccompProfile RuntimeDefault не задан")
    return problems


CRD_URL = "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{group}/{kind}_{version}.json"


def load_crd_schema(crd_dir: str, group: str, kind: str, version: str):
    path = os.path.join(crd_dir, group, f"{kind}_{version}.json")
    if not os.path.exists(path):
        try:
            with urllib.request.urlopen(CRD_URL.format(group=group, kind=kind, version=version), timeout=20) as r:
                data = r.read()
        except Exception:
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    with open(path, encoding="utf8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="YAML-файлы или - для stdin")
    parser.add_argument("--k8s-version", default="1.30.0")
    parser.add_argument("--crd-dir", default=".crd-schemas", help="кэш схем CRD")
    parser.add_argument("--pss", action="store_true", help="проверить поды на Pod Security Standards restricted")
    args = parser.parse_args()

    documents = []
    for name in args.files:
        text = sys.stdin.read() if name == "-" else open(name, encoding="utf8").read()
        documents += [(name, d) for d in yaml.safe_load_all(text) if isinstance(d, dict) and "kind" in d]

    valid = invalid = skipped = pss_bad = 0
    for source, doc in documents:
        title = f"{doc.get('kind')}/{doc.get('metadata', {}).get('name')}"
        if args.pss:
            for problem in check_pss_restricted(doc):
                pss_bad += 1
                print(f"PSS   {source}: {title}: {problem}")
        try:
            kubernetes_validate.validate(doc, args.k8s_version, strict=True)
            valid += 1
            continue
        except ValidationError as exc:
            invalid += 1
            print(f"FAIL  {source}: {title}: {exc.message} (путь {list(exc.path)})")
            continue
        except (SchemaNotFoundError, InvalidSchemaError):
            pass  # не встроенный ресурс — ищем схему CRD
        group, _, version = doc["apiVersion"].rpartition("/")
        schema = load_crd_schema(args.crd_dir, group, doc["kind"].lower(), version)
        if schema is None:
            skipped += 1
            print(f"SKIP  {source}: {title}: нет схемы для {doc['apiVersion']}")
            continue
        errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
        if errors:
            invalid += 1
            for err in errors[:3]:
                print(f"FAIL  {source}: {title}: {err.message} (путь {list(err.path)})")
        else:
            valid += 1
    print(f"Итого: ресурсов {len(documents)}, корректных {valid}, с ошибками {invalid}, без схемы {skipped}")
    if args.pss:
        workloads = sum(1 for _, d in documents if d.get("kind") in POD_KINDS)
        print(f"PSS restricted: рабочих нагрузок {workloads}, нарушений {pss_bad}")
    return 1 if invalid or pss_bad else 0


if __name__ == "__main__":
    sys.exit(main())
