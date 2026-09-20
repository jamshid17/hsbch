"""The shape the client reads a failure out of.

api.ts branches on `detail.code`, fills the sentence from `detail.params`,
and falls back to `detail.message` for a code it has no string for. All three
are load-bearing, and none of them is visible from the frontend's side of the
wire, so they are pinned here.
"""

from app.errors import api_error


def test_a_user_facing_error_carries_a_code_and_a_sentence():
    exc = api_error(415, "upload.not_an_image", "Faqat rasm yuklang.")

    assert exc.status_code == 415
    assert exc.detail == {
        "code": "upload.not_an_image",
        "message": "Faqat rasm yuklang.",
    }


def test_params_travel_with_it_for_the_placeholders():
    exc = api_error(413, "upload.too_large", "Juda katta.", mb="7.3", max=5)

    assert exc.detail["params"] == {"mb": "7.3", "max": 5}


def test_no_params_means_no_params_key():
    """An empty dict would read as "there are placeholders" to anything
    checking for the key."""
    assert "params" not in api_error(400, "upload.empty", "Bo'sh.").detail


def test_the_fallback_sentence_is_never_omitted():
    """A code the client has no string for still has to read as words: the
    whole point is that nobody is shown a key."""
    exc = api_error(500, "scan.unexpected", "Kutilmagan xato.")

    assert exc.detail["message"]
