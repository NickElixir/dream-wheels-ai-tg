"""Структурное описание автомобильного диска.

Используется промпт-билдером (`src.prompts.build_prompt`) для повышения
точности генерации Reve. Stage 1: атрибуты заполняются дефолтами через
`extract_rim_description`-стаб. Stage 2 заменит стаб на CV-извлечение
spoke_count / profile / finish из самого фото диска.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SpokeProfile = Literal["flat", "concave", "split", "mesh", "directional"]
Finish = Literal[
    "gloss-black",
    "matte-black",
    "silver",
    "polished",
    "bronze",
    "two-tone",
]


class RimDescription(BaseModel):
    """Структурные характеристики диска для текстового промпта.

    Поля выбраны так, чтобы текстовый фрагмент однозначно отличал визуально
    разные стили дисков — это то, что генеративная модель использует для
    «привязки» к референсу.
    """

    spoke_count: int = Field(default=5, ge=3, le=20)
    profile: SpokeProfile = "flat"
    finish: Finish = "silver"
    centre_cap: bool = True

    def to_prompt_fragment(self) -> str:
        """Текстовый фрагмент, встраиваемый в основной промпт Reve."""
        cap = "with a centre cap" if self.centre_cap else "without a centre cap"
        return (
            f"The wheels have a {self.spoke_count}-spoke {self.profile} "
            f"design, {self.finish} finish, {cap}."
        )


def extract_rim_description(wheel_image_b64: str) -> RimDescription:
    """Извлечь структурные атрибуты диска из base64-изображения.

    Stage 1: возвращает дефолтный `RimDescription`. Сигнатура зафиксирована,
    чтобы Stage 2 (CV-классификатор) мог подменить реализацию без правок
    в воркере и промпт-билдере.
    """
    del wheel_image_b64  # placeholder; Stage 2 будет анализировать b64
    return RimDescription()
