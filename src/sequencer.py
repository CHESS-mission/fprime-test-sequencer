import re
import time

from fprime_gds.common.data_types.ch_data import ChData
from fprime_gds.common.data_types.event_data import EventData
from fprime_gds.common.testing_fw.api import IntegrationTestAPI
from src.parser.parser import ExpectEventInstruction, ExpectTelemetryInstruction, Sequence


def run_sequence(seq: Sequence, api: IntegrationTestAPI):
    starting_time_s = time.time()
    def elapsed_time_s():
        return time.time() - starting_time_s

    commands = seq.get_ordered_commands()
    max_send_time_digits = len(str(commands[-1].send_time_ms))

    for command in commands:
        # Sleep until next command
        time.sleep(max(0.001 * command.send_time_ms - elapsed_time_s(), 0))
        # Send command
        print(f"[{round(1000 * elapsed_time_s()):{max_send_time_digits}} ms]: Sending command {command.command} {' '.join(command.args)}")
        api.send_command(command.command, command.args)


def find_event(expected_event: ExpectEventInstruction, events: list[EventData], starting_time: float) -> EventData | None:
    for event in events:
        match_ = True
        match_ &= 0.001 * expected_event.start_time_ms <= event.get_time().get_float() - starting_time <= 0.001 * expected_event.end_time_ms
        match_ &= expected_event.event == event.get_severity() or expected_event.event == event.template.get_full_name()
        if expected_event.expected_value != None:
            if expected_event.is_regex:
                match_ &= re.search(expected_event.expected_value, event.get_display_text()) != None
            else:
                match_ &= expected_event.expected_value == event.get_display_text()
        if match_:
            return event
    return None

def find_telemetry(expected_telemetry: ExpectTelemetryInstruction, tel_readings: list[ChData], starting_time: float) -> ChData | None:
    for reading in tel_readings:
        match_ = True
        match_ &= 0.001 * expected_telemetry.start_time_ms <= reading.get_time().get_float() - starting_time <= 0.001 * expected_telemetry.end_time_ms
        match_ &= expected_telemetry.channel == reading.template.get_full_name()
        if expected_telemetry.expected_value != None:
            if expected_telemetry.is_regex:
                match_ &= re.search(expected_telemetry.expected_value, str(reading.get_display_text())) != None
            else:
                match_ &= expected_telemetry.expected_value == reading.get_display_text()
        if match_:
            return reading
    return None


def validate_sequence(seq: Sequence, starting_time: float, api: IntegrationTestAPI):
    ok = "\033[92m[OK]\033[0m"
    fail = "\033[91m[FAIL]\033[0m"

    print("[VALIDATING EVENTS]")

    for expected_event in seq.event_instrs:
        matching_event = find_event(expected_event, api.get_event_test_history().retrieve(), starting_time)
        if matching_event != None:
            timing = f"[{round(1000 * (matching_event.get_time().get_float() - starting_time))} ms]"
            severity = matching_event.get_severity()
            name = matching_event.template.get_full_name()
            value = "" if matching_event.get_display_text() == "" else f"\"{matching_event.get_display_text()}\""
            match_ = f"{timing} {severity} {name} {value}"
        else:
            match_ = "None"
        timing = f"[{expected_event.start_time_ms}:{expected_event.end_time_ms}]"
        event = f"EXPECT{'' if expected_event.is_expected else ' NO'} EVENT {expected_event.event}"
        value = "" if expected_event.expected_value == None else f" {'re' if expected_event.is_regex else ''}\"{expected_event.expected_value}\""
        result = f"{ok if (matching_event != None) == expected_event.is_expected else fail}"
        print(f"{timing} {event}{value}: {result} ~> {match_}")

    print("[VALIDATING TELEMETRY]")

    for expected_telemetry in seq.telemetry_instrs:
        matching_telemetry = find_telemetry(expected_telemetry, api.get_telemetry_test_history().retrieve(), starting_time)
        if matching_telemetry != None:
            timing = f"[{round(1000 * (matching_telemetry.get_time().get_float() - starting_time))} ms]"
            name = matching_telemetry.template.get_full_name()
            value = "" if matching_telemetry.get_display_text() == "" else f"\"{matching_telemetry.get_display_text()}\""
            match_ = f"{timing} {name} {value}"
        else:
            match_ = "None"
        timing = f"[{expected_telemetry.start_time_ms}:{expected_telemetry.end_time_ms}]"
        event = f"EXPECT{'' if expected_telemetry.is_expected else ' NO'} TELEMETRY {expected_telemetry.channel}"
        value = "" if expected_telemetry.expected_value == None else f" {'re' if expected_telemetry.is_regex else ''}\"{expected_telemetry.expected_value}\""
        result = f"{ok if (matching_telemetry != None) == expected_telemetry.is_expected else fail}"
        print(f"{timing} {event}{value}: {result} ~> {match_}")
