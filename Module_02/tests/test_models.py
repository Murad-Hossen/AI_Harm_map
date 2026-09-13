import pytest

torch = pytest.importorskip("torch")

from ai_harm_map.constants import ROLES
from ai_harm_map.models import (
    PHTKG,
    PHTKGConfig,
    PairwiseBaseline,
)


def test_pairwise_output_shape():
    model = PairwiseBaseline(
        total_nodes=20,
        n_roles=len(ROLES),
        embedding_dim=8,
    )
    ids = torch.randint(
        0,
        20,
        (4, len(ROLES)),
    )
    assert model(ids).shape == (4,)


def test_phtkg_output_shapes():
    model = PHTKG(
        total_nodes=20,
        config=PHTKGConfig(
            embedding_dim=8,
            layers=1,
        ),
    )

    ids = torch.randint(
        0,
        20,
        (3, len(ROLES)),
    )
    years = torch.zeros(3)
    known = torch.ones(3)
    provenance = torch.ones(3)
    time_mean = torch.zeros(20)
    time_known = torch.ones(20)

    output = model(
        ids,
        years,
        known,
        provenance,
        time_mean,
        time_known,
    )

    assert output["embedding"].shape == (3, 8)
    assert output["score"].shape == (3,)
    assert output["entity_state"].shape == (20, 8)
