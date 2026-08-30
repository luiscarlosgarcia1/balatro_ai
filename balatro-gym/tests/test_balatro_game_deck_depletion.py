from balatro_gym.core.balatro_game import BalatroGame
from balatro_gym.core.cards import Card, Rank, Suit


def _deck(size: int):
    ranks = list(Rank)
    suits = list(Suit)
    return [Card(ranks[i % len(ranks)], suits[i % len(suits)]) for i in range(size)]


def test_discarded_card_is_not_immediately_redrawn():
    game = BalatroGame()
    game.deck = _deck(10)
    game.hand_size = 5
    game.reset_round()

    discarded_index = game.hand_indexes[0]
    game.highlight_card(0)

    assert game.discard_hand() is True

    assert discarded_index not in game.hand_indexes
    assert discarded_index in game.discard_pile_indexes
    assert game.hand_indexes == [1, 2, 3, 4, 5]
    assert game.draw_pile_indexes == [6, 7, 8, 9]


def test_played_card_moves_to_discard_before_next_draw():
    game = BalatroGame()
    game.deck = _deck(10)
    game.hand_size = 5
    game.reset_round()

    played_index = game.hand_indexes[0]
    game.highlight_card(0)

    result = game.play_hand()

    assert result is not None
    assert played_index not in game.hand_indexes
    assert played_index in game.discard_pile_indexes
    assert game.play_area_indexes == []
    assert game.hand_indexes == [1, 2, 3, 4, 5]
    assert game.draw_pile_indexes == [6, 7, 8, 9]
