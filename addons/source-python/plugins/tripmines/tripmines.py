from math import asin, atan2, degrees, floor
from random import choice
from time import time

from colors import Color
from commands.client import ClientCommand
from effects import temp_entities
from engines.sound import Attenuation, Sound
from engines.trace import (
    ContentMasks, engine_trace, GameTrace, MAX_TRACE_LENGTH, Ray,
    TraceFilterSimple)

from engines.precache import Model
from entities import TakeDamageInfo
from entities.constants import WORLD_ENTITY_INDEX
from entities.entity import Entity
from entities.hooks import EntityCondition, EntityPreHook
from events import Event
from filters.recipients import RecipientFilter
from listeners import OnClientDisconnect, OnEntityOutput
from listeners.tick import Delay
from memory import make_object
from paths import PLUGIN_DATA_PATH
from players import UserCmd
from players.constants import PlayerButtons
from players.entity import Player
from players.helpers import index_from_userid
from players.teams import teams_by_name
from stringtables.downloads import Downloadables

from mathlib import NULL_VECTOR, Vector

from .info import info
from .cvars import config_manager
from .internal_events import InternalEvent
from .strings import strings
from .take_damage import take_damage
from .trip_mine_player import broadcast, player_manager, tell


PROP_MODEL = Model('models/weapons/w_slam.mdl')
BEAM_MODEL = Model('sprites/laserbeam.vmt')
EXPLOSION_MODEL = Model('sprites/zerogxplode.spr')
EXPLOSION_SOUNDS = [
    'weapons/explode3.wav',
    'weapons/explode4.wav',
    'weapons/explode5.wav',
]
PLANT_OFFSET = 1.5
PLANT_ANGLES = Vector(90, 0, 0)


_announcement_delay = None
_downloadables = Downloadables()
with open(PLUGIN_DATA_PATH / info.basename / "downloadlist.res") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        _downloadables.add(line)


class TripMine:
    def __init__(self, id, owner, origin, normal):
        self.id = id
        self.owner = owner
        self.origin = origin
        self.normal = normal

        self.activated = False

        self.prop = None
        self.beam = None
        self.beam_target = None

        self._delays = []

        self.create()

    def __del__(self):
        self.cancel_delays()

    def cancel_delays(self):
        for delay in self._delays:
            if delay.running:
                delay.cancel()

        self._delays.clear()

    def _beep(self):
        if self.prop is None:
            return

        if config_manager['beep_sound'] != "":
            Sound(config_manager['beep_sound'],
                  index=self.prop.index,
                  attenuation=Attenuation.STATIC).play()

            self._delays.append(
                Delay(config_manager['beep_interval'], self._beep))

    def create(self):
        self.create_prop()
        self._delays.append(
            Delay(config_manager['activation_delay'], self.create_beam))

        self._delays.append(
            Delay(
                config_manager['activation_delay'] +
                config_manager['beep_interval'],
                self._beep
            )
        )

    def create_prop(self):
        origin = self.origin + self.normal * PLANT_OFFSET
        self.prop = Entity.create("prop_physics_override")
        self.prop.target_name = "_tripmines_prop_{}".format(self.id)
        self.prop.model = PROP_MODEL
        self.prop.spawn_flags = 8
        self.prop.teleport(origin, PLANT_ANGLES + Vector(
            -degrees(asin(self.normal.z)),
            degrees(atan2(self.normal.y, self.normal.x)),
            0,
        ), None)

        # Make it non-solid so that the beam goes through
        self.prop.solid_type = 6
        self.prop.collision_group = 11

        self.prop.spawn()

        if config_manager['plant_sound'] != "":
            Sound(
                config_manager['plant_sound'],
                index=self.prop.index,
                attenuation=Attenuation.STATIC).play()

    def create_beam(self):
        if self.prop is None:
            raise RuntimeError("Create prop first")

        end_trace_vec = self.origin + self.normal * MAX_TRACE_LENGTH

        trace = GameTrace()
        engine_trace.trace_ray(
            Ray(self.origin, end_trace_vec),
            ContentMasks.ALL,
            TraceFilterSimple(ignore=(self.prop.index, )),
            trace
        )

        if not trace.did_hit():
            return

        if self.owner.team == teams_by_name['ct']:
            beam_color = Color(100, 100, 255)
        else:
            beam_color = Color(255, 100, 100)

        self.beam_target = Entity.create("env_spark")
        self.beam_target.target_name = "_tripmines_target1_{}".format(self.id)
        self.beam_target.teleport(self.origin, None, None)
        self.beam_target.spawn()

        self.beam = Entity.create("env_beam")
        self.beam.target_name = "_tripmines_beam_{}".format(self.id)
        self.beam.spawn_flags = 1
        self.beam.teleport(trace.end_position, None, None)

        self.beam.set_key_value_float('BoltWidth', 1.0)
        self.beam.set_key_value_int('damage', 0)
        self.beam.set_key_value_float('HDRColorScale', 1.0)
        self.beam.set_key_value_int('life', 0)
        self.beam.set_key_value_string(
            'LightningStart', self.beam.target_name)
        self.beam.set_key_value_string(
            'LightningEnd', self.beam_target.target_name)
        self.beam.set_key_value_int('Radius', 255)
        self.beam.set_key_value_int('renderamt', 100)
        self.beam.set_key_value_color('rendercolor', beam_color)
        self.beam.set_key_value_int('StrikeTime', 1)
        self.beam.set_key_value_string('texture', "sprites/laserbeam.spr")
        self.beam.set_key_value_int('TextureScroll', 35)
        self.beam.set_key_value_int('TouchType', 3)

        self.beam.model = BEAM_MODEL
        self.beam.set_property_vector('m_vecEndPos', self.origin)

        self.beam.spawn()

        self.beam.call_input('TurnOff')
        self.beam.call_input('TurnOn')

        self.activated = True

        if config_manager['activation_sound'] != "":
            Sound(config_manager['activation_sound'],
                  index=self.prop.index,
                  attenuation=Attenuation.STATIC).play()

    def _hurt_around(self, ignore=()):
        for player in player_manager.values():
            if player.player.index in ignore:
                continue

            if player.player.dead:
                continue

            if player.player.team not in (
                    teams_by_name['t'], teams_by_name['ct']):

                continue

            if (not config_manager['allow_teamkill'] and
                    self.owner != player.player and
                    self.owner.team == player.player.team):

                continue

            distance = (self.origin - player.player.origin).length
            damage = max(0, floor(
                config_manager['damage_base'] -
                distance * config_manager['damage_falloff_multiplier']
            ))

            if not damage:
                continue

            take_damage(
                player.player,
                damage,
                attacker=self.owner,
            )

    def _detonate(self, entity):
        self.activated = False

        # Explosion visual effects
        temp_entities.explosion(
            RecipientFilter(),      # Recipients
            0.0,                    # Delay
            self.prop.origin,       # Origin
            EXPLOSION_MODEL.index,  # Model index
            2.0,                    # Scale
            0,                      # Framerate
            4,                      # Flags, 4 = no sound
            512,                    # Radius
            1,                      # Magnitude
            NULL_VECTOR,            # Normal
            67,                     # Material Type (chr(67) = "C")
        )

        # Explosion sound
        Sound(choice(EXPLOSION_SOUNDS),
              index=self.prop.index,
              attenuation=Attenuation.STATIC).play()

    def destroy(self):
        player_manager[self.owner.index].total_mines_planted -= 1

        # Remove child entities
        for child_entity in (self.prop, self.beam, self.beam_target):
            child_entity.remove()

        self.prop = None
        self.beam = None
        self.beam_target = None

        self.cancel_delays()
        trip_mine_manager.remove(self)

    def on_touched_by_entity(self, entity):
        # Without turning the beam off and on again,
        # the output listener will never fire any more
        self.beam.call_input('TurnOff')
        self.beam.call_input('TurnOn')

        entity_receives_damage = True
        if entity.classname == 'player':
            entity = Player(entity.index)
            if (not config_manager['allow_teamkill'] and
                    entity != self.owner and
                    entity.team == self.owner.team):

                return

            entity_receives_damage = not entity.dead

        self._detonate(entity)
        self.destroy()

        if entity_receives_damage:
            take_damage(entity,
                        config_manager['damage_base'],
                        attacker=self.owner)

        self._hurt_around(ignore=(entity.index, ))

    def on_prop_damaged(self, player):
        if (not config_manager['allow_teamkill'] and
                player != self.owner and
                player.team == self.owner.team):

            return

        self._detonate(player)
        self.destroy()
        self._hurt_around()


class TripMineManager(list):
    def __init__(self):
        super().__init__()

        self._current_id = 0

    def create(self, owner, origin, normal):
        self.append(TripMine(self._current_id, owner, origin, normal))
        self._current_id += 1

    def get_by_beam_index(self, index):
        for trip_mine in self:
            if trip_mine.beam is not None and trip_mine.beam.index == index:
                return trip_mine

        raise IndexError(
            "Couldn't find appropriate tripmine to "
            "beam index {}".format(index))

    def get_by_prop_index(self, index):
        for trip_mine in self:
            if trip_mine.prop is not None and trip_mine.prop.index == index:
                return trip_mine

        raise IndexError(
            "Couldn't find appropriate tripmine to "
            "prop index {}".format(index))

    def iter_by_owner_index(self, index):
        for trip_mine in self:
            if trip_mine.owner.index == index:
                yield trip_mine

    def reset(self):
        for trip_mine in tuple(self):
            trip_mine.cancel_delays()

        self.clear()
        self._current_id = 0

        for player in player_manager.values():
            player.total_mines_planted = 0

    def destroy_all(self):
        for trip_mine in tuple(self):
            trip_mine.destroy()

        self._current_id = 0

trip_mine_manager = TripMineManager()


def load():
    InternalEvent.fire('load')
    broadcast(strings['load'])


def unload():
    trip_mine_manager.destroy_all()

    global _announcement_delay
    if _announcement_delay is not None and _announcement_delay.running:
        _announcement_delay.cancel()

    InternalEvent.fire('unload')
    broadcast(strings['unload'])


def get_mine_denial_reason(player):
    if not config_manager['enable']:
        return strings['fail disabled']

    if time() - player.last_mine_time <= config_manager['plant_timeout']:
        return strings['fail too_soon']

    if player.player.dead:
        return strings['fail dead']

    if player.player.team not in (teams_by_name['t'], teams_by_name['ct']):
        return strings['fail wrong_team']

    if config_manager['mines_stock'] != -1 and player.mines <= 0:
        return strings['fail no_mines']

    if player.total_mines_planted >= config_manager['mines_limit'] > 0:
        return strings['fail too_many']

    return None


def use_mine(player, end_position, normal):
    player.mines -= 1
    player.total_mines_planted += 1
    player.last_mine_time = time()

    # Negative mines number indicates that infinite mines are turned on
    if player.mines >= 0:
        tell(player, strings['mines_left'].tokenize(mines=player.mines))

    trip_mine_manager.create( player.player, end_position, normal)


def try_use_mine(player):
    reason = get_mine_denial_reason(player)
    if reason is not None:
        tell(player, reason)
        return

    trace = player.player.get_trace_ray()
    distance = (trace.end_position - player.player.origin).length
    if distance > config_manager['plant_distance']:
        tell(player, strings['fail too_far'])
        return

    use_mine(player, trace.end_position, trace.plane.normal)


@OnEntityOutput
def listener_on_entity_output(output_name, activator, caller, value, delay):
    if output_name != "OnTouchedByEntity":
        return

    if not isinstance(caller, Entity) or not isinstance(activator, Entity):
        return

    try:
        trip_mine = trip_mine_manager.get_by_beam_index(caller.index)
    except IndexError:
        return

    trip_mine.on_touched_by_entity(activator)


@OnClientDisconnect
def listener_on_client_disconnect(index):
    for trip_mine in tuple(trip_mine_manager.iter_by_owner_index(index)):
        trip_mine.destroy()


@ClientCommand('+tripmine')
def client_tripmine(command, index):
    try_use_mine(player_manager[index])


@InternalEvent('player_respawn')
def on_player_respawn(event_var):
    player = event_var['player']
    player.mines = config_manager['mines_stock']


@Event('round_start')
def on_round_start(game_event):
    trip_mine_manager.reset()

    global _announcement_delay
    if _announcement_delay is not None and _announcement_delay.running:
        _announcement_delay.cancel()

    if config_manager['announcement_delay'] >= 0:
        _announcement_delay = Delay(
            config_manager['announcement_delay'],
            broadcast,
            strings['announcement']
        )


@Event('player_death')
def on_player_death(game_event):
    if not config_manager['remove_on_death']:
        return

    index = index_from_userid(game_event['userid'])
    for trip_mine in tuple(trip_mine_manager.iter_by_owner_index(index)):
        trip_mine.destroy()


@EntityPreHook(EntityCondition.is_human_player, 'run_command')
def pre_run_command(args):
    player = player_manager[make_object(Player, args[0]).index]

    user_cmd = make_object(UserCmd, args[1])

    if not (user_cmd.buttons & PlayerButtons.SCORE and
            user_cmd.buttons & PlayerButtons.USE):

        return

    if get_mine_denial_reason(player) is not None:
        return

    trace = player.player.get_trace_ray()
    distance = (trace.end_position - player.player.origin).length
    if distance > config_manager['plant_distance']:
        return

    use_mine(player, trace.end_position, trace.plane.normal)


@EntityPreHook(
    EntityCondition.equals_entity_classname('prop_physics_override'),
    'on_take_damage')
def pre_take_damage(args):
    victim_entity = make_object(Entity, args[0])
    try:
        victim_trip_mine = trip_mine_manager.get_by_prop_index(
            victim_entity.index)
    except IndexError:
        return

    if not victim_trip_mine.activated:
        return False

    info = make_object(TakeDamageInfo, args[1])

    if info.attacker == WORLD_ENTITY_INDEX:
        return False

    attacker_entity = Entity(info.attacker)
    if attacker_entity.classname != 'player':
        return False

    attacker_player = player_manager[info.attacker]
    victim_trip_mine.on_prop_damaged(attacker_player.player)
    return False
