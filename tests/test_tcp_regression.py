"""TCP regressions: every ADB command and retry delay is simulated."""

import subprocess
from unittest.mock import patch

import pytest

from firestrip.core.adb import ADBClient
from firestrip.core.exceptions import (
    ADBBinaryNotFoundError,
    ADBConnectionError,
    ADBTimeoutError,
)

TARGET = "192.168.1.13:5555"


def cp(out="", code=0):
    return subprocess.CompletedProcess([], code, out, "")


def listing(state="device", target=TARGET):
    return cp(f"List of devices attached\n{target}\t{state}\n")


@pytest.fixture(autouse=True)
def simulated_delay():
    with patch("time.sleep"):
        yield


@pytest.mark.parametrize(
    "raw",
    [
        listing("unauthorized"),
        listing("offline"),
        listing(target="192.168.1.13:55550"),
        listing(target="1192.168.1.13:5555"),
        listing(target="192.168.1.138:5555"),
        listing(target="192.168.1.13:5556"),
        cp(TARGET),
        cp(f"{TARGET}\tnonsense\n"),
        cp("garbage"),
        cp(listing().stdout, 1),
    ],
)
def test_unready_or_wrong_target_never_succeeds(raw):
    with patch("subprocess.run", side_effect=[raw, cp("already connected"), raw, raw, raw]):
        with pytest.raises(ADBConnectionError):
            ADBClient(host="192.168.1.13").connect()


def test_exact_ready_fast_path():
    with patch("subprocess.run", return_value=listing()) as run:
        assert ADBClient(host="192.168.1.13").connect()
        assert run.call_count == 1


@pytest.mark.parametrize("message", ["connected to " + TARGET, "already connected", "", "OK"])
def test_connect_requires_verified_state(message):
    with patch("subprocess.run", side_effect=[cp(), cp(message), listing()]) as run:
        assert ADBClient(host="192.168.1.13").connect()
        assert run.call_count == 3


@pytest.mark.parametrize("initial", ["offline", "unauthorized"])
def test_state_can_become_ready_after_connect(initial):
    with patch(
        "subprocess.run",
        side_effect=[listing(initial), cp("connected"), listing(initial), listing()],
    ) as run:
        assert ADBClient(host="192.168.1.13").connect()
        assert run.call_count == 4


def test_connect_nonzero_does_not_accept_success_text():
    with patch("subprocess.run", side_effect=[cp(), cp("connected to " + TARGET, 1)]):
        with pytest.raises(ADBConnectionError):
            ADBClient(host="192.168.1.13").connect()


@pytest.mark.parametrize(
    "exc,expected",
    [
        (FileNotFoundError(), ADBBinaryNotFoundError),
        (subprocess.TimeoutExpired("adb", 15), ADBTimeoutError),
    ],
)
@pytest.mark.parametrize("phase", ["connect", "verify"])
def test_execution_errors(exc, expected, phase):
    replies = [cp(), exc] if phase == "connect" else [cp(), cp("connected"), exc]
    with patch("subprocess.run", side_effect=replies):
        with pytest.raises(expected):
            ADBClient(host="192.168.1.13").connect()


def test_initial_timeout_can_recover():
    replies = [subprocess.TimeoutExpired("adb", 5), cp(), listing()]
    with patch("subprocess.run", side_effect=replies):
        assert ADBClient(host="192.168.1.13").connect()


def test_different_requested_port_can_connect():
    with patch("subprocess.run", return_value=listing(target="192.168.1.13:5556")):
        assert ADBClient(host="192.168.1.13", port=5556).connect()


def test_ready_on_third_verification_is_accepted():
    replies = [cp(), cp("connected"), listing("unauthorized"), listing("offline"), listing()]
    with patch("subprocess.run", side_effect=replies) as run, patch("time.sleep") as sleep:
        assert ADBClient(host="192.168.1.13").connect()
        assert run.call_count == 5
        assert sleep.call_args_list == [((0.25,),), ((0.25,),)]


def test_later_authorization_requires_retry_and_does_not_report_false_success():
    replies = [
        cp(),
        cp("connected"),
        listing("unauthorized"),
        listing("unauthorized"),
        listing("unauthorized"),
        listing(),
    ]
    client = ADBClient(host="192.168.1.13")
    with patch("subprocess.run", side_effect=replies) as run, patch("time.sleep") as sleep:
        with pytest.raises(ADBConnectionError, match="retry") as error:
            client.connect()
        message = str(error.value)
        for detail in (
            "disconnected",
            "offline",
            "awaiting authorization",
            "absent from the device list",
        ):
            assert detail in message
        assert "If an ADB authorization prompt appears" in message
        assert run.call_count == 5
        assert sleep.call_count == 2
        assert client.connect()
        assert run.call_count == 6


def test_failed_initial_listing_can_recover_via_connect():
    replies = [cp(listing().stdout, 1), cp("connected"), listing()]
    with patch("subprocess.run", side_effect=replies) as run:
        assert ADBClient(host="192.168.1.13").connect()
        assert run.call_count == 3


@pytest.mark.parametrize("code", [-1, 1, 2])
def test_verification_error_never_accepts_ready_stdout(code):
    replies = [cp(), cp("connected"), cp(listing().stdout, code)]
    with patch("subprocess.run", side_effect=replies):
        with pytest.raises(ADBConnectionError, match="verification failed"):
            ADBClient(host="192.168.1.13").connect()


def test_connect_error_in_stderr_is_rejected_even_with_zero_exit():
    failed = subprocess.CompletedProcess([], 0, "", "unable to connect")
    with patch("subprocess.run", side_effect=[cp(), failed]):
        with pytest.raises(ADBConnectionError, match="Failed to connect"):
            ADBClient(host="192.168.1.13").connect()


@pytest.mark.parametrize("host,other", [("tv", "mytv"), ("10.0.0.1", "110.0.0.1")])
def test_similar_hostnames_and_serials_do_not_match(host, other):
    raw = listing(target=f"{other}:5555")
    with patch("subprocess.run", side_effect=[raw, cp("connected"), raw, raw, raw]):
        with pytest.raises(ADBConnectionError):
            ADBClient(host=host).connect()
