from entities import TakeDamageInfo
from entities.constants import DamageTypes


def take_damage(entity, damage, attacker):
    take_damage_info = TakeDamageInfo()
    take_damage_info.attacker = attacker.index
    take_damage_info.damage = damage
    take_damage_info.type = DamageTypes.BLAST
    entity.on_take_damage(take_damage_info)
