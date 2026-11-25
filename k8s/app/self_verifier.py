"""Верификатор Self Agent ID (selfxyz-agent-sdk): возраст 18+, провайдер Self, один человек — один агент.

В учебной среде — сеть testnet и mock-паспорт (с настоящим паспортом testnet вернёт
InvalidIdentityCommitmentRoot). Верификатор создаётся лениво: SDK тянет web3 и ходит в RPC.
"""
from functools import lru_cache

from fastapi import Request

from app.config import settings


@lru_cache(maxsize=1)
def get_verifier():
    from self_agent_sdk import SelfAgentVerifier

    return (
        SelfAgentVerifier.create()
        .network(settings.self_network)
        .require_age(18)
        .require_self_provider()      # proof выпущен именно Self Protocol
        .sybil_limit(1)               # один человек — один агент
        .include_credentials()        # нужны раскрытые данные: older_than
        .build()
    )


async def agent_auth(request: Request):
    """FastAPI-зависимость: AgentAuth из SDK с отложенным созданием верификатора."""
    from self_agent_sdk.middleware.fastapi import AgentAuth

    return await AgentAuth(get_verifier())(request)
