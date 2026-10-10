# Sample times and Berlin wall time

Suite 2.3.13 adds a clock reference to each study.
Original phase-relative CSV fields and experiment timing remain unchanged.

During setup, Respyra makes up to three small HTTPS requests to
`https://timeapi.io/api/time/current/zone?timeZone=UTC`. It selects the successful
response with the shortest measured round trip. TimeAPI.io is currently
[free](https://timeapi.io/home/faqs); its
[site](https://timeapi.io/) advertises 99.99% uptime. These are provider claims,
not an independent uptime measurement or a free-tier SLA. Cloudflare's
[public NTP service](https://developers.cloudflare.com/time-services/ntp/usage/)
is an alternative time protocol, rather than the requested HTTPS API.

The reference freezes when recording starts, without waiting for the network.
If HTTPS fails, returns invalid/cached data, is too slow, or has not completed,
the run uses its initial computer-clock reference. A late response cannot alter
an active run. No API request runs in a sample or display loop. No account, API
key, participant ID, answer or signal is sent to the provider. Ordinary network
requests expose the connecting IP address to the service.

UTC is mapped to LSL's monotonic clock; wall-clock corrections never reset the
study timer or change trial durations. All Berlin display times use the bundled
IANA `Europe/Berlin` rules, including CET/CEST and daylight saving transitions.
The computer's configured time zone does not affect this conversion. The app
does not change the Windows clock or its synchronization settings.

## CSV fields

Sample and assessment CSVs append four fields to their existing columns:

| Field | Meaning |
| --- | --- |
| `lsl_time_s` | Individual accepted sample time from the clock-synchronized inlet, serialized at double precision. For assessment rows, the time when their summary row is written. |
| `utc_time` | Estimated UTC time, ISO 8601 with microseconds and `+00:00`. |
| `berlin_time` | Estimated Berlin time, ISO 8601 with microseconds and the applicable `+01:00` or `+02:00` offset. |
| `time_reference` | `timeapi.io` if a usable response arrived before Start; `system` otherwise. |

The original `timestamp` is still phase-relative display-frame time. Samples
consumed in one frame can share it while their `lsl_time_s` differs. Force and
tracking errors retain the original calculations/rounding. Polar columns retain
their g-based names. A matching `<csv filename>.json` stores the frozen reference
and identifies sample timing versus assessment log-write timing. Individual
answer-key events remain timestamped in XDF.

`scripts/xdf_to_csv.py` adds UTC/Berlin/reference fields and JSON provenance when
the XDF contains a new clock reference. Run it in the installed/project Python
environment, which includes `mpi` and PyXDF. Older XDFs retain LSL-only exports;
the app does not invent historical wall time from file creation dates.

## XDF and BIDS

`recording.started.clock_reference` embeds the same mapping in XDF, so wall time
can be reconstructed without a CSV sidecar. PyXDF synchronizes producer clocks;
the BIDS exporter applies that correction to the marker's reference anchor as
well. This follows LSL's documented
[mapping between LSL and other clocks](https://labstreaminglayer.readthedocs.io/info/time_synchronization.html).

New BIDS signal tables retain `timestamp` and every `channelN`, then append
`lsl_time_s`, `utc_unix_s` (estimated Unix epoch seconds) and
`berlin_utc_offset_s`. Fixed-rate physiology stays numeric. Sidecars include
`ClockReference`, `TimeOriginLSL`, `TimeOriginUTC` and `TimeOriginBerlin`.
Events tables include ISO UTC/Berlin times. The MNE reader imports only the
recorded signal channels; timestamp columns do not become physiological channels.
Older XDFs without a reference keep their existing BIDS layout.

## Accuracy

These are estimated absolute timestamps, not an exact-time certificate. HTTPS
provides one server timestamp, not NTP's full four-timestamp exchange. The
mapping uses the request midpoint. `round_trip_s` records measured transport
time; `transport_uncertainty_s` is half that round trip plus one microsecond of
serialization allowance. It excludes server-clock accuracy, LSL alignment error,
asymmetric latency and subsequent oscillator drift. Their combined error is
unknown. Offline computer-clock accuracy is also unknown. Microsecond formatting
does not imply microsecond absolute accuracy.

For signal/event alignment, keep the XDF timestamps and clock-offset records.
For externally calibrated absolute-time accuracy, an independently measured
NTP/PTP or hardware synchronization procedure is still needed.
