"""
LocalStack integration coverage for list_objects' hand-rolled pagination.

`list_objects_v2` caps a single response at 1000 keys; `s3.list_objects`
follows `IsTruncated`/`NextContinuationToken` to go past that. A mocked unit
test only proves we build a plausible-looking request — it can't prove S3
actually accepts the continuation token this library hands back to it. This
does, against a real (local) S3-compatible endpoint.

Populating >1000 objects is the slow part of this suite, so both tests below
share one bucket populated once per module.
"""

from collections.abc import Callable, Generator

import pytest

from aws_simple import s3

pytestmark = pytest.mark.integration

PAGE_SIZE = 1000
TOTAL_OBJECTS = PAGE_SIZE + 37  # forces a second page


@pytest.fixture(scope="module")
def populated_bucket(bucket_factory: Callable[[], str]) -> Generator[str, None, None]:
    from aws_simple.config import configure

    name = bucket_factory()
    configure(bucket=name)
    for i in range(TOTAL_OBJECTS):
        s3.put_object(f"paged/{i:05d}.txt", "x", bucket=name)
    yield name


def test_list_objects_paginates_past_1000_keys(populated_bucket: str) -> None:
    keys = s3.list_objects(prefix="paged/", bucket=populated_bucket)

    assert len(keys) == TOTAL_OBJECTS


def test_list_objects_max_keys_trims_across_pages(populated_bucket: str) -> None:
    """max_keys stops pagination partway through the second page."""
    requested = PAGE_SIZE + 10

    keys = s3.list_objects(prefix="paged/", bucket=populated_bucket, max_keys=requested)

    assert len(keys) == requested
