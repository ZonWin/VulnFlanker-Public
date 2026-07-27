from __future__ import annotations

from fastapi import APIRouter

from app.matching.product_aliases import product_alias_groups
from app.schemas.matching import ProductAliasOut

router = APIRouter()


@router.get("/product-aliases", response_model=list[ProductAliasOut])
async def get_product_aliases() -> list[ProductAliasOut]:
    return [ProductAliasOut(**item) for item in product_alias_groups()]
