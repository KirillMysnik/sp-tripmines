from controlled_cvars import ControlledConfigManager
from controlled_cvars.handlers import (
    bool_handler, float_handler, int_handler, string_handler)

from .info import info


config_manager = ControlledConfigManager(info.basename, cvar_prefix="tm_")
config_manager.controlled_cvar(
    bool_handler,
    "enable",
    default=1,
    description="Enable/Disable TripMines functionality"
)
config_manager.controlled_cvar(
    bool_handler,
    "allow_teamkill",
    default=0,
    description="Allow/Disallow team kills with trip mines "
                "(also allows/dissalows destroying friendly mines)"
)
config_manager.controlled_cvar(
    int_handler,
    "mines_stock",
    default=3,
    description="Initial number of mines given to a player"
)
config_manager.controlled_cvar(
    int_handler,
    "damage_base",
    default=120,
    description="Absolute damage amount for direct contact AND "
                "damage falloff base for long-distance shots"
)
config_manager.controlled_cvar(
    float_handler,
    "damage_falloff_multiplier",
    default=0.25,
    description="Damage falloff multiplier for long-distance shots "
                "(when mine is being shot from a distance). "
                "If you set it to 2 and damage base to 100, "
                "a player standing 32 units away from the mine will receive "
                "100 - 32*2 = 36 HP of damage."
)
config_manager.controlled_cvar(
    float_handler,
    "plant_distance",
    default=80.0,
    description="Maximum distance (in units) between a player and a surface "
                "to plant the mine"
)
config_manager.controlled_cvar(
    bool_handler,
    "remove_on_death",
    default=1,
    description="Enable/Disable removing planted mines on owner's death"
)
config_manager.controlled_cvar(
    float_handler,
    "plant_timeout",
    default=1,
    description="Timeout (in seconds) after the mine has been planted "
                "before player can plant another mine"
)
config_manager.controlled_cvar(
    float_handler,
    "activation_delay",
    default=2.0,
    description="How much time (in seconds) does it take for the mine "
                "to activate"
)
config_manager.controlled_cvar(
    float_handler,
    "beep_interval",
    default=4.0,
    description="Time (in seconds) after the mine has beeped "
                "before it beeps again"
)
config_manager.controlled_cvar(
    string_handler,
    "plant_sound",
    default="weapons/slam/mine_mode.wav",
    description="Sound to play when the mine is planted, "
                "leave empty to disable"
)
config_manager.controlled_cvar(
    string_handler,
    "activation_sound",
    default="buttons/button14.wav",
    description="Sound to play when the mine is activated, "
                "leave empty to disable"
)
config_manager.controlled_cvar(
    string_handler,
    "beep_sound",
    default="buttons/button17.wav",
    description="Sound to play when the mine beeps, leave empty to disable"
)
config_manager.controlled_cvar(
    float_handler,
    "announcement_delay",
    default=5.0,
    description="Delay (in seconds) before announcing TAB+E combination "
                "in the beginning of the round (-1 to disable)"
)

config_manager.write()
config_manager.execute()