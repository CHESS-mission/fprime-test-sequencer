import os
from pathlib import Path
import re
import time

from fprime_gds.common.data_types.ch_data import ChData
from fprime_gds.common.data_types.event_data import EventData
from fprime_gds.common.testing_fw.api import IntegrationTestAPI
from fprime_test_sequencer.parser.parser import CommandInstruction, ExpectEventInstruction, ExpectTelemetryInstruction, Sequence, UplinkInstruction
from fprime_test_sequencer.util import ch_data_to_str, event_data_to_str, make_green, make_red

class Sequencer:
    def __init__(self, api: IntegrationTestAPI) -> None:
        self.api = api


    def run_and_validate_sequence(self, seq: Sequence) -> bool:
        header = f" [RUNNING TEST {seq.name}] "
        print(f"{header:=^80s}")

        starting_time = time.time()
        self.run_sequence(seq)

        remaining_time = max(0, starting_time + 0.001 * seq.get_duration() - time.time())
        print(f"Waiting {remaining_time:.2f} seconds for the sequence to finish...")
        time.sleep(remaining_time)

        success = self.validate_sequence(seq, starting_time)

        footer = f" [TEST {seq.name} {'PASSED' if success else 'FAILED'}] "
        print(f"{make_green(footer) if success else make_red(footer):=^89s}")

        return success


    def run_sequence(self, seq: Sequence):
        starting_time_s = time.time()
        def elapsed_time_s():
            return time.time() - starting_time_s

        instructions: list[tuple[int, CommandInstruction | UplinkInstruction]] = []

        instructions += [(
            cmd.send_time_ms,
            cmd
        ) for cmd in seq.command_instrs]

        instructions += [(
            up.uplink_time_ms,
            up
        ) for up in seq.uplink_instrs]

        # Sort instructions by execution time
        instructions.sort(key=lambda e: e[0])

        max_exec_time_digits = len(str(instructions[-1][0]))

        for exec_time, instr in instructions:
            # Sleep until next instruction
            time.sleep(max(0.001 * exec_time - elapsed_time_s(), 0))
            # Execute instruction
            if type(instr) == CommandInstruction:
                print(f"[{round(1000 * elapsed_time_s()):{max_exec_time_digits}} ms]: Sending command {instr.command} {' '.join(instr.args)}")
                self.api.send_command(instr.command, instr.args)
            elif type(instr) == UplinkInstruction:
                print(f"[{round(1000 * elapsed_time_s()):{max_exec_time_digits}} ms]: Uplinking file {instr.file} to {instr.dest}")
                tmp_file = str(self.api.pipeline.up_store) + "/" + Path(instr.file).name
                os.system(f"cp {instr.file} {tmp_file}")
                self.api.pipeline.files.uplinker.enqueue(tmp_file, instr.dest)


    def find_matching_event(self, event: ExpectEventInstruction, starting_time: float) -> EventData | None:
        for received_event in self.api.get_event_test_history().retrieve():
            match_ = True
            match_ &= 0.001 * event.start_time_ms <= received_event.get_time().get_float() - starting_time <= 0.001 * event.end_time_ms
            match_ &= event.event == received_event.get_severity() or event.event == received_event.template.get_full_name()
            if event.expected_value != None:
                if event.is_regex:
                    match_ &= re.search(event.expected_value, received_event.get_display_text()) != None
                else:
                    match_ &= event.expected_value == received_event.get_display_text()
            if match_:
                return received_event
        return None

    def find_matching_telemetry(self, telemetry: ExpectTelemetryInstruction, starting_time: float) -> ChData | None:
        for received_telemetry in self.api.get_telemetry_test_history().retrieve():
            match_ = True
            match_ &= 0.001 * telemetry.start_time_ms <= received_telemetry.get_time().get_float() - starting_time <= 0.001 * telemetry.end_time_ms
            match_ &= telemetry.channel == received_telemetry.template.get_full_name()
            if telemetry.expected_value != None:
                if telemetry.is_regex:
                    match_ &= re.search(telemetry.expected_value, str(received_telemetry.get_display_text())) != None
                else:
                    match_ &= telemetry.expected_value == received_telemetry.get_display_text()
            if match_:
                return received_telemetry
        return None


    def validate_sequence(self, seq: Sequence, starting_time: float) -> bool:
        success = True

        print(f"{' [VALIDATING EVENTS] ':-^80s}")

        for expected_event in seq.event_instrs:
            matching_event = self.find_matching_event(expected_event, starting_time)
            success &= (matching_event != None) == expected_event.is_expected

            result = f"{make_green('[OK]') if (matching_event != None) == expected_event.is_expected else make_red('[FAIL]')}"
            match_ = event_data_to_str(matching_event, starting_time) if matching_event is not None else "None"
            print(f"{expected_event}: {result} ~> {match_}")

        print(f"{' [VALIDATING TELEMETRY] ':-^80s}")

        for expected_telemetry in seq.telemetry_instrs:
            matching_telemetry = self.find_matching_telemetry(expected_telemetry, starting_time)
            success &= (matching_telemetry != None) == expected_telemetry.is_expected

            result = f"{make_green('[OK]') if (matching_telemetry  != None) == expected_telemetry.is_expected else make_red('[FAIL]')}"
            match_ = ch_data_to_str(matching_telemetry, starting_time) if matching_telemetry is not None else "None"
            print(f"{expected_telemetry}: {result} ~> {match_}")

        return success
