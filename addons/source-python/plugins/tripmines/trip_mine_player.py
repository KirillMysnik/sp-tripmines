from events import Event
from filters.players import PlayerIter
from listeners import OnClientActive, OnClientDisconnect, OnLevelShutdown
from messages import SayText2
from players.entity import Player
from players.helpers import index_from_userid
from players.teams import teams_by_name

from .internal_events import InternalEvent
from .strings import COLOR_SCHEME, strings


class TripMinePlayer:
    def __init__(self, player):
        self.player = player
        self.mines = 0
        self.last_mine_time = 0
        self.total_mines_planted = 0

    def __eq__(self, other):
        return self.player.index == other.player.index


class TripMinePlayerManager(dict):
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        InternalEvent.fire('player_registered', player=value)

    def __delitem__(self, key):
        InternalEvent.fire('player_unregistered', player=self[key])
        dict.__delitem__(self, key)

    def get_by_userid(self, userid):
        return self[index_from_userid(userid)]

player_manager = TripMinePlayerManager()


@OnClientActive
def listener_on_client_active(index):
    player_manager[index] = TripMinePlayer(Player(index))


@OnClientDisconnect
def listener_on_client_disconnect(index):
    del player_manager[index]


@OnLevelShutdown
def listener_on_level_shutdown():
    for index in tuple(player_manager.keys()):
        del player_manager[index]


@InternalEvent('load')
def on_load(event_var):
    for player in PlayerIter():
        player_manager[player.index] = TripMinePlayer(player)


@InternalEvent('unload')
def on_unload(event_var):
    for index in tuple(player_manager.keys()):
        del player_manager[index]


@Event('player_spawn')
def on_player_spawn(game_event):
    player = player_manager.get_by_userid(game_event['userid'])
    if player.player.team != teams_by_name['un']:
        InternalEvent.fire(
            'player_respawn',
            player=player,
            game_event=game_event,
        )


def tell(players, message, **tokens):
    if isinstance(players, TripMinePlayer):
        players = (players, )

    player_indexes = [player.player.index for player in players]

    tokens.update(COLOR_SCHEME)

    message = message.tokenize(**tokens)
    message = strings['chat_base'].tokenize(message=message, **COLOR_SCHEME)

    SayText2(message=message).send(*player_indexes)


def broadcast(message, **tokens):
    tell(player_manager.values(), message, **tokens)
