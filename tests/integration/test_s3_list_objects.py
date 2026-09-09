"""
Integration tests for :func:`aws_simple.s3.list_objects` against real S3.

``list_objects`` hand-rolls ``ContinuationToken`` pagination and ``max_keys``
trimming. A mock returns whatever shape the test author wrote, so only a real
endpoint can prove the continuation token is accepted and that the paging
arithmetic adds up.
"""

import pytest

from aws_simple import s3
from aws_simple.exceptions import S3Error

from .conftest import ManyKeys

pytestmark = pytest.mark.integration


def test_returns_empty_list_for_empty_bucket(bucket: str) -> None:
    """An empty bucket yields no keys: the response has no ``Contents``."""
    assert s3.list_objects(bucket=bucket) == []


def test_returns_empty_list_for_unmatched_prefix(bucket: str) -> None:
    """A prefix nothing matches yields no keys."""
    s3.put_object("kept/a.txt", b"a", bucket=bucket)

    assert s3.list_objects(prefix="absent/", bucket=bucket) == []


def test_filters_by_prefix(bucket: str) -> None:
    """Only keys under the prefix come back."""
    s3.put_object("docs/a.txt", b"a", bucket=bucket)
    s3.put_object("docs/b.txt", b"b", bucket=bucket)
    s3.put_object("images/c.png", b"c", bucket=bucket)

    assert s3.list_objects(prefix="docs/", bucket=bucket) == ["docs/a.txt", "docs/b.txt"]


def test_paginates_past_the_1000_key_page_size(many_keys: ManyKeys) -> None:
    """
    More than one page of keys is returned in full, not truncated.

    This is the ``ContinuationToken`` path: S3 caps a single
    ``list_objects_v2`` response at 1000 keys, so returning all of them means
    the token was round-tripped correctly.
    """
    keys = s3.list_objects(prefix=many_keys.prefix, bucket=many_keys.bucket)

    assert keys == many_keys.keys
    assert len(keys) > 1000, "fixture must exceed one page for this test to mean anything"


def test_pagination_does_not_duplicate_or_drop_keys(many_keys: ManyKeys) -> None:
    """Each key appears exactly once across the page boundary."""
    keys = s3.list_objects(prefix=many_keys.prefix, bucket=many_keys.bucket)

    assert len(set(keys)) == len(keys)
    assert set(keys) == set(many_keys.keys)


def test_paginates_the_whole_bucket_when_no_prefix_is_given(many_keys: ManyKeys) -> None:
    """An empty prefix lists everything, across pages and prefixes alike."""
    keys = s3.list_objects(bucket=many_keys.bucket)

    assert keys == sorted(many_keys.keys + many_keys.other_keys)


def test_returns_keys_in_lexicographic_order(many_keys: ManyKeys) -> None:
    """S3 orders keys lexicographically, and pagination preserves that."""
    keys = s3.list_objects(bucket=many_keys.bucket)

    assert keys == sorted(keys)


@pytest.mark.parametrize("max_keys", [1, 2, 10, 999, 1000, 1001, 1002, 1500])
def test_max_keys_trims_to_the_first_n_keys(many_keys: ManyKeys, max_keys: int) -> None:
    """
    ``max_keys`` caps the *total* across pages and trims exactly.

    The values straddle the 1000-key page size on purpose: below it a single
    request suffices, at 1001 and above the cap can only be reached by
    following a continuation token, and 1500 exceeds the number of objects
    that exist so the listing must stop early instead of over-fetching.
    """
    keys = s3.list_objects(prefix=many_keys.prefix, bucket=many_keys.bucket, max_keys=max_keys)

    assert keys == many_keys.keys[:max_keys]


def test_max_keys_zero_returns_nothing(many_keys: ManyKeys) -> None:
    """A cap of zero short-circuits before any request is made."""
    assert s3.list_objects(prefix=many_keys.prefix, bucket=many_keys.bucket, max_keys=0) == []


def test_max_keys_above_the_total_returns_every_key(many_keys: ManyKeys) -> None:
    """A cap larger than the bucket is not padded, and does not loop forever."""
    total = len(many_keys.keys) + len(many_keys.other_keys)

    keys = s3.list_objects(bucket=many_keys.bucket, max_keys=total + 500)

    assert keys == sorted(many_keys.keys + many_keys.other_keys)


def test_missing_bucket_raises_s3_error() -> None:
    """A bucket that does not exist surfaces as ``S3Error``, not ``ClientError``."""
    with pytest.raises(S3Error, match="Failed to list objects"):
        s3.list_objects(bucket="aws-simple-it-definitely-absent-bucket")


def test_uses_default_bucket_from_env(default_bucket: str) -> None:
    """With no ``bucket`` argument the ``AWS_S3_BUCKET`` bucket is listed."""
    key = "list-default/only.txt"
    s3.put_object(key, b"x")
    try:
        assert s3.list_objects(prefix="list-default/") == [key]
    finally:
        s3.delete_object(key)
