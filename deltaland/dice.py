"""Dice rolling logic"""

import random
import time
from typing import Tuple

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from .consts import DICE_COOLDOWN, DICE_FEE, StateEnum
from .orm import Cooldown, DiceRank, Player, fetchone
from .util import human_time_duration

_DICES = {
    1: "⚀",
    2: "⚁",
    3: "⚂",
    4: "⚃",
    5: "⚄",
    6: "⚅",
}


def roll_dice(count: int = 2) -> Tuple[int, ...]:
    return tuple(random.randint(1, 6) for _ in range(count))


def dices2str(dices: Tuple[int, ...]) -> str:
    return " + ".join(_DICES[val] for val in dices) + f" ({sum(dices)})"


async def play_dice(player: Player, session) -> None:
    player.gold -= DICE_FEE
    player.state = StateEnum.PLAYING_DICE
    if not player.dice_rank:
        player.dice_rank = DiceRank(gold=0)
    stmt = (
        select(Cooldown)
        .options(selectinload(Cooldown.player).selectinload(Player.dice_rank))
        .filter_by(id=StateEnum.PLAYING_DICE)
    )
    cooldown = await fetchone(session, stmt)
    if cooldown:
        await _play_dice(player, cooldown.player)
        await session.delete(cooldown)
    else:
        await player.send_message(
            text=(
                "You sat down waiting for other players.\n"
                f"If you won't find anyone, you'll leave in {human_time_duration(DICE_COOLDOWN)}"
            )
        )
        player.cooldowns.append(
            Cooldown(id=StateEnum.PLAYING_DICE, ends_at=time.time() + DICE_COOLDOWN)
        )


async def _play_dice(player1: Player, player2: Player) -> None:
    roll1 = roll_dice()
    roll2 = roll_dice()
    while sum(roll1) == sum(roll2):
        roll1 = roll_dice()
        roll2 = roll_dice()
    if sum(roll1) < sum(roll2):
        player1, player2 = player2, player1
        roll1, roll2 = roll2, roll1

    player1.dice_rank.gold += DICE_FEE
    player2.dice_rank.gold -= DICE_FEE

    earned_gold = 2 * DICE_FEE
    player1.gold += earned_gold
    player1.state = player2.state = StateEnum.REST

    name1, name2 = player1.get_name(), player2.get_name()
    dices1, dices2 = dices2str(roll1), dices2str(roll2)
    text = "\n".join(
        [
            "🎲 You threw the dice on the table:\n",
            f"{name1}: {dices1}",
            f"{name2}: {dices2}\n",
            f"{{}}{name1} won! {earned_gold:+}💰",
        ]
    )
    await player1.send_message(text=text.format("🎉 "))
    await player2.send_message(text=text.format(""))
