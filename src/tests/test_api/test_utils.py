import pytest

from brp_kennisgevingen.api.utils import is_valid_bsn


class TestIsValidBSN:

    @pytest.mark.parametrize(
        "bsn",
        [
            "999990019",
            "999990020",
            "999990032",
            "999990044",
            "999990056",
        ],
    )
    def test_valid_bsn(self, bsn):
        assert is_valid_bsn(bsn)

    @pytest.mark.parametrize(
        "bsn",
        [
            None,
            "123",
            "abc",
            "999999999",
        ],
    )
    def test_invalid_bsn(self, bsn):
        assert not is_valid_bsn(bsn)
