"""Tests del publisher_node — sin llamadas reales a GitHub."""

from unittest.mock import MagicMock, patch

import pytest
from github import GithubException

from src.giros_bot.graph.nodes.publisher import _commit_to_github_sync, publisher_node
from src.giros_bot.schemas.state import AgentState

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_repo_mock(ref_sha: str = "abc123") -> MagicMock:
    """Crea un mock completo del objeto repo de PyGithub."""
    repo = MagicMock()

    # get_git_ref → ref object
    ref = MagicMock()
    ref.object.sha = ref_sha
    repo.get_git_ref.return_value = ref

    # get_git_commit → commit object con tree
    parent_commit = MagicMock()
    parent_commit.tree.sha = "tree_base_sha"
    repo.get_git_commit.return_value = parent_commit

    # get_git_tree → base tree object (GitTree)
    base_tree = MagicMock()
    repo.get_git_tree.return_value = base_tree

    # create_git_blob → blob
    mdx_blob = MagicMock()
    mdx_blob.sha = "mdx_blob_sha"
    repo.create_git_blob.return_value = mdx_blob

    # create_git_tree → tree
    new_tree = MagicMock()
    repo.create_git_tree.return_value = new_tree

    # create_git_commit → commit
    new_commit = MagicMock()
    new_commit.sha = "new_commit_sha_full_40chars_xxxxxxxxxxxxx"
    repo.create_git_commit.return_value = new_commit

    # edit no retorna nada (None)
    ref.edit.return_value = None

    return repo


# ── Tests de _commit_to_github_sync ──────────────────────────────────────────

def test_commit_to_github_sync_success():
    """El commit se crea y la ref se actualiza en el primer intento."""
    repo = _make_repo_mock()

    with (
        patch("src.giros_bot.graph.nodes.publisher.Github") as MockGithub,
        patch("src.giros_bot.graph.nodes.publisher.settings") as mock_settings,
    ):
        mock_settings.github_token = "fake_token"
        mock_settings.github_repo_owner = "owner"
        mock_settings.github_repo_name = "repo"
        MockGithub.return_value.get_repo.return_value = repo

        sha = _commit_to_github_sync(
            mdx_final="---\ntitle: Test\n---\nContenido",
            mdx_path="content/blog/2026-02-test.mdx",
            img_path="public/blog/test.jpg",
            image_bytes_b64="",
            commit_msg="content(blog): Test [2026-02-27]",
        )

    assert sha == repo.create_git_commit.return_value.sha
    repo.get_git_ref.assert_called_once_with("heads/main")
    repo.get_git_tree.assert_called_once_with("tree_base_sha")
    repo.create_git_tree.assert_called_once_with(
        repo.create_git_tree.call_args[0][0],  # tree_elements
        repo.get_git_tree.return_value,         # base_tree GitTree object
    )
    repo.create_git_blob.assert_called_once()  # Solo MDX, sin imagen
    repo.get_git_ref.return_value.edit.assert_called_once_with(sha)


def test_commit_to_github_sync_includes_image_blob():
    """Si hay imagen, se crean dos blobs (MDX + imagen)."""
    import base64

    repo = _make_repo_mock()
    img_b64 = base64.b64encode(b"fake_image_bytes").decode()

    blob1 = MagicMock()
    blob1.sha = "mdx_sha"
    blob2 = MagicMock()
    blob2.sha = "img_sha"
    repo.create_git_blob.side_effect = [blob1, blob2]

    with (
        patch("src.giros_bot.graph.nodes.publisher.Github") as MockGithub,
        patch("src.giros_bot.graph.nodes.publisher.settings") as mock_settings,
    ):
        mock_settings.github_token = "fake_token"
        mock_settings.github_repo_owner = "owner"
        mock_settings.github_repo_name = "repo"
        MockGithub.return_value.get_repo.return_value = repo

        _commit_to_github_sync(
            mdx_final="---\ntitle: Test\n---\nContenido",
            mdx_path="content/blog/2026-02-test.mdx",
            img_path="public/blog/test.jpg",
            image_bytes_b64=img_b64,
            commit_msg="content(blog): Test [2026-02-27]",
        )

    assert repo.create_git_blob.call_count == 2


def test_commit_retries_on_non_fast_forward():
    """Si edit() falla con GithubException, reintenta hasta _GH_REF_RETRIES veces."""
    repo = _make_repo_mock()
    exc = GithubException(422, {"message": "Update is not a fast forward"}, {})

    # Falla las dos primeras veces, tiene éxito en la tercera
    repo.get_git_ref.return_value.edit.side_effect = [exc, exc, None]

    with (
        patch("src.giros_bot.graph.nodes.publisher.Github") as MockGithub,
        patch("src.giros_bot.graph.nodes.publisher.settings") as mock_settings,
        patch("src.giros_bot.graph.nodes.publisher.time.sleep"),  # No esperar en tests
    ):
        mock_settings.github_token = "fake_token"
        mock_settings.github_repo_owner = "owner"
        mock_settings.github_repo_name = "repo"
        MockGithub.return_value.get_repo.return_value = repo

        sha = _commit_to_github_sync(
            mdx_final="---\ntitle: Test\n---\nContenido",
            mdx_path="content/blog/2026-02-test.mdx",
            img_path="public/blog/test.jpg",
            image_bytes_b64="",
            commit_msg="content(blog): Test [2026-02-27]",
        )

    # Re-fetch la ref en cada intento
    assert repo.get_git_ref.call_count == 3
    assert sha == repo.create_git_commit.return_value.sha


def test_commit_raises_after_all_retries_exhausted():
    """Si todos los reintentos fallan, se propaga la última GithubException."""
    from src.giros_bot.graph.nodes.publisher import _GH_REF_RETRIES

    repo = _make_repo_mock()
    exc = GithubException(422, {"message": "Update is not a fast forward"}, {})
    repo.get_git_ref.return_value.edit.side_effect = exc

    with (
        patch("src.giros_bot.graph.nodes.publisher.Github") as MockGithub,
        patch("src.giros_bot.graph.nodes.publisher.settings") as mock_settings,
        patch("src.giros_bot.graph.nodes.publisher.time.sleep"),
    ):
        mock_settings.github_token = "fake_token"
        mock_settings.github_repo_owner = "owner"
        mock_settings.github_repo_name = "repo"
        MockGithub.return_value.get_repo.return_value = repo

        with pytest.raises(GithubException):
            _commit_to_github_sync(
                mdx_final="---\ntitle: Test\n---\nContenido",
                mdx_path="content/blog/2026-02-test.mdx",
                img_path="public/blog/test.jpg",
                image_bytes_b64="",
                commit_msg="content(blog): Test [2026-02-27]",
            )

    assert repo.get_git_ref.call_count == _GH_REF_RETRIES


# ── Tests de publisher_node ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publisher_node_github_error_sets_error_message():
    """Si GitHub falla, publisher_node devuelve error_message sin propagar la excepción."""
    state = AgentState(
        target_date="2026-02-27",
        slug="test-slug",
        title="Test Title",
        mdx_content_body="---\ntitle: Test\n---\nContenido",
        image_bytes_b64="",
    )

    with patch(
        "src.giros_bot.graph.nodes.publisher._commit_to_github_sync",
        side_effect=GithubException(401, {"message": "Bad credentials"}, {}),
    ):
        result = await publisher_node(state)

    assert "error_message" in result
    assert "GithubException" in result["error_message"]
    assert "image_url_generated" not in result


@pytest.mark.asyncio
async def test_publisher_node_success_sets_image_url():
    """En caso de éxito, publisher_node retorna image_url_generated correcta."""
    import base64

    img_b64 = base64.b64encode(b"fake_image").decode()
    state = AgentState(
        target_date="2026-02-27",
        slug="test-slug",
        title="Test Title",
        mdx_content_body="---\ntitle: Test\n---\nContenido __IMAGE_ALT__",
        image_alt="Foto de prueba",
        image_bytes_b64=img_b64,
    )

    with (
        patch(
            "src.giros_bot.graph.nodes.publisher._commit_to_github_sync",
            return_value="deadbeef" * 5,
        ),
        patch(
            "src.giros_bot.graph.nodes.publisher._wait_for_image",
            return_value=False,
        ),
    ):
        result = await publisher_node(state)

    assert result.get("image_url_generated") == "https://girosmedia.cl/blog/test-slug.jpg"
    assert "error_message" not in result


@pytest.mark.asyncio
async def test_publisher_node_replaces_image_alt_placeholder():
    """El placeholder __IMAGE_ALT__ es reemplazado antes de pasar el MDX a GitHub."""
    state = AgentState(
        target_date="2026-02-27",
        slug="test-slug",
        title="Test Title",
        mdx_content_body='imageAlt: "__IMAGE_ALT__"',
        image_alt="Descripción real",
        image_bytes_b64="",
    )

    captured: dict = {}

    def capture_mdx(mdx_final, mdx_path, img_path, image_bytes_b64, commit_msg):
        captured["mdx_final"] = mdx_final
        return "sha" * 10

    with patch(
        "src.giros_bot.graph.nodes.publisher._commit_to_github_sync",
        side_effect=capture_mdx,
    ):
        await publisher_node(state)

    assert "__IMAGE_ALT__" not in captured["mdx_final"]
    assert "Descripción real" in captured["mdx_final"]
