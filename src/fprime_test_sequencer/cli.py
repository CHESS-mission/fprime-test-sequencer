#!/usr/bin/env python3

import time
import os
import argparse
import platform
from pathlib import Path

from fprime.common.models.serialize.time_type import TimeType

from fprime_gds.common.history.chrono import ChronologicalHistory
from fprime_gds.common.pipeline.standard import StandardPipeline
from fprime_gds.common.testing_fw.api import IntegrationTestAPI
from fprime_gds.common.utils.config_manager import ConfigManager
from fprime_gds.executables.utils import find_dict, get_artifacts_root

from fprime_test_sequencer.parser.exceptions import ParseError
from fprime_test_sequencer.parser.lexer import FileReader, Lexer
from fprime_test_sequencer.parser.parser import CommandInstruction, Parser, Sequence, UplinkInstruction
from fprime_test_sequencer.sequencer import Sequencer
from fprime_test_sequencer.util import ch_data_to_str, event_data_to_str, make_green, make_red, time_to_relative_ms


class LocalTimeChronologicalHistory(ChronologicalHistory):
    """
    A chronological history which replaces remote sending times with local reception times.
    """

    def data_callback(self, data, sender=None):
        if self.filter(data):
            data.time.set_float(time.time())
        super().data_callback(data, sender)


def find_dictionary() -> Path | None:
    detected_toolchain = get_artifacts_root() / platform.system()

    if not detected_toolchain.exists():
        print(f"{detected_toolchain} does not exist. Make sure to build.")
        return None

    likely_deployment = detected_toolchain / Path.cwd().name
    # Check if the deployment exists
    if likely_deployment.exists():
        deployment = likely_deployment
    else :
        child_directories = [child for child in detected_toolchain.iterdir() if child.is_dir()]

        if not child_directories:
            print(f"No deployments found in {detected_toolchain}. Specify deployment with: --deployment")
            return None
        if len(child_directories) > 1:
            print(f"Multiple deployments found in {detected_toolchain}. Choose using: --deployment")
            return None

        # Works for the old structure where the bin, lib, and dict directories live immediately under the platform
        if len(child_directories) == 3 and set([path.name for path in child_directories]) == {"bin", "lib", "dict"}:
            deployment = detected_toolchain
        else:
            deployment = child_directories[0]

    return find_dict(deployment)


def write_logs(filename: str, api: IntegrationTestAPI, commands: list[CommandInstruction], uplinks: list[UplinkInstruction], starting_time: float):
    print(f"Writing logs to {filename}...")

    to_ms = time_to_relative_ms(starting_time)

    entries: list[tuple[int, str]] = []

    entries += [(
        cmd.send_time_ms,
        f"COMMAND {cmd.command} {' '.join(cmd.args)}"
    ) for cmd in commands]

    entries += [(
        to_ms(ed.get_time().get_float()),
        f"EVENT {event_data_to_str(ed, with_timing=False)}"
    ) for ed in api.get_event_test_history().retrieve()]

    entries += [(
        to_ms(cd.get_time().get_float()),
        f"TELEMETRY {ch_data_to_str(cd, with_timing=False)}"
    ) for cd in api.get_telemetry_test_history().retrieve()]

    entries += [(
        up.uplink_time_ms,
        f"UPLINK {up.file} {up.dest}"
    ) for up in uplinks]

    # Sort log entries by occurence time
    entries.sort(key=lambda e: e[0])

    with open(filename, 'w') as f:
        f.writelines([f"[{e[0]} ms] {e[1]}\n" for e in entries])


def parse_file(file: str) -> dict[str, Sequence]:
    try:
        reader = FileReader(file)
    except FileNotFoundError:
        print(f"File not found: {file}")
        exit()

    lexer = Lexer(reader)
    parser = Parser(lexer)

    sequences = None
    try:
        sequences = parser.parse()
    except ParseError as pe:
        print(pe)

    if sequences == None:
        exit()

    return sequences


def check(file: str):
    sequences = parse_file(file)

    print(f"Syntax check [{make_green('OK')}]")

    i = 1
    for seq_name, seq in sequences.items():
        print(f"\n{i}.")
        header = f" [SEQUENCE {seq_name}] "
        print(f"{header:=^80s}")
        print(f"  is_test: {seq.is_test}")
        print(f"  duration: {seq.get_duration()} ms")

        print(f"{' [COMMANDS] ':-^80s}")
        for command_instr in seq.get_ordered_commands():
            print(f"  [{command_instr.send_time_ms} ms]: {command_instr.command} {' '.join(command_instr.args)}")

        print(f"{' [EVENTS] ':-^80s}")
        for event_instr in seq.event_instrs:
            print(f"  {event_instr}")

        print(f"{' [TELEMETRY] ':-^80s}")
        for telemetry_instr in seq.telemetry_instrs:
            print(f"  {telemetry_instr}")

        print(f"{' [UPLINK] ':-^80s}")
        for uplink_instr in seq.get_ordered_uplinks():
            print(f"  [{uplink_instr.uplink_time_ms} ms]: UPLINK {uplink_instr.file} {uplink_instr.dest}")

        print(f"{'-'*80}")
        i += 1


def setup_integration_test_api(dictionary: str, file_storage_dir: str, tts_addr: str, tts_port: str) -> IntegrationTestAPI:
    pipeline = StandardPipeline()
    try:
        pipeline.setup(config=ConfigManager(), dictionary=dictionary, file_store=file_storage_dir)
        pipeline.connect(f"{tts_addr}:{tts_port}")
    except Exception:
        # In all error cases, pipeline should be shutdown before continuing with exception handling
        try:
            pipeline.disconnect()
        finally:
            raise

    api = IntegrationTestAPI(pipeline)
    api.setup()

    # Replace fprime-gds' chronological history with local time chronological history
    api.event_history = LocalTimeChronologicalHistory()
    api.telemetry_history = LocalTimeChronologicalHistory()
    api.pipeline.coders.register_event_consumer(api.event_history)
    api.pipeline.coders.register_channel_consumer(api.telemetry_history)

    return api


def add_cli_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("file", help="fpseq file from which sequences are read")
    parser.add_argument("-c", "--check", action="store_true", help="perform syntax check and print parsed sequences")
    parser.add_argument("-t", "--test", help="only run TEST")
    parser.add_argument("-d", "--dictionary", help="path to dictionary")
    parser.add_argument("--file-storage-directory", help="directory to store uplink and downlink files [default: /tmp/updown]", default="/tmp/updown")
    parser.add_argument("--tts-addr", help="fprime-gds threaded TCP socket server address [default: 0.0.0.0]", default="0.0.0.0")
    parser.add_argument("--tts-port", help="fprime-gds threaded TCP socket server port [default: 50050]", default="50050")
    parser.add_argument("--log-all", help="log all sent commands, received events and telemetry to given file", metavar="LOG_ALL_FILE")


def main():
    parser = argparse.ArgumentParser()
    add_cli_arguments(parser)
    args = parser.parse_args()

    if args.check:
        check(args.file)
        exit()

    sequences = parse_file(args.file)

    if args.log_all is not None:
        dirname = os.path.dirname(args.log_all)
        if not os.path.exists(dirname) and not dirname == "":
            print(f"Path {dirname} does not exist")
            exit()
        print(f"Logging commands, events and telemetry to {args.log_all}")

    if args.dictionary is None:
        print("Automatically detecting dictionary file...")
        args.dictionary = find_dictionary()
        if args.dictionary is None:
            print("Couldn't detect dictionary")
            exit()
    elif not os.path.exists(args.dictionary):
        print(f"Dictionary file {args.dictionary} does not exist")
        exit()

    print(f"Using dictionary {args.dictionary}")

    api = setup_integration_test_api(str(args.dictionary), args.file_storage_directory, args.tts_addr, args.tts_port)

    sequencer = Sequencer(api)

    test_count = 0
    successes = 0
    starting_time = time.time()
    sent_commands = []
    uplinks = []
    if args.test is not None:
        if args.test not in sequences.keys():
            print(f"No test named {args.test} in {args.file}")
            exit()
        print()
        success = sequencer.run_and_validate_sequence(sequences[args.test])
        test_count = 1
        successes = 1 if success else 0
        sent_commands += sequences[args.test].command_instrs
        uplinks += sequences[args.test].uplink_instrs
    else:
        cumulative_seq_duration = 0
        for sequence in sequences.values():
            if sequence.is_test:
                print(f"\n{test_count+1}.")
                success = sequencer.run_and_validate_sequence(sequence)
                test_count += 1
                successes += 1 if success else 0
                sent_commands += [i.with_time_offset(cumulative_seq_duration) for i in sequence.command_instrs]
                uplinks += [u.with_time_offset(cumulative_seq_duration) for u in sequence.uplink_instrs]
                cumulative_seq_duration += sequence.get_duration()

    success_rate = f" [{successes}/{test_count} TESTS PASSED ({float(successes)/float(test_count):.0%})] "
    print(f"\n{make_green(success_rate) if successes == test_count else make_red(success_rate):=^89s}\n")

    if args.log_all is not None:
        write_logs(args.log_all, api, sent_commands, uplinks, starting_time)

    api.pipeline.disconnect()


if __name__ == "__main__":
    main()
