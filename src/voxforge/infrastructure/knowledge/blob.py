"""Filesystem blob storage for knowledge base uploads."""

from __future__ import annotations

from pathlib import Path

from voxforge.core.interfaces.knowledge import BlobStore


class FilesystemBlobStore:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        path = self._root / key
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._root / key
        if path.exists():
            path.unlink()

    async def exists(self, key: str) -> bool:
        return (self._root / key).exists()


def create_blob_store(blob_store: str, *, path: str) -> BlobStore:
    if blob_store == "filesystem":
        return FilesystemBlobStore(path)
    raise ValueError(f"Unsupported blob store: {blob_store}")
