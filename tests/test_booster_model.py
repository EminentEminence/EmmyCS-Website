from booster_model import CardRecord


def test_dual_finish_cards_are_treated_as_foil():
    record = CardRecord.from_mapping({
        "name": "Test Card",
        "finishes": ["nonfoil", "foil"],
        "rarity": "rare",
    })

    assert record is not None
    assert record.foil is True


def test_single_foil_finish_cards_are_treated_as_foil():
    record = CardRecord.from_mapping({
        "name": "Test Card",
        "finishes": ["foil"],
        "rarity": "rare",
    })

    assert record is not None
    assert record.foil is True
