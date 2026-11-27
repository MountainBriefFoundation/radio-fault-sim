import unittest
from dataclasses import FrozenInstanceError

from radio_fault_sim import Faults, FeedbackMode, PartialWriteError, SimTnc, WriteMode


def prepared(**kwargs):
    sim = SimTnc(**kwargs)
    sim.attach("controller")
    return sim


class ConfigurationTests(unittest.TestCase):
    def test_constructor_rejects_invalid_timing_and_limits(self):
        for name in ("queue_delay_ms", "ptt_duration_ms", "feedback_delay_ms", "max_payload_bytes"):
            for value in (True, False, 1.5, "1", None):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    SimTnc(**{name: value})
            with self.subTest(name=name), self.assertRaises(ValueError):
                SimTnc(**{name: -1})
        for name in ("ptt_duration_ms", "max_payload_bytes"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                SimTnc(**{name: 0})

    def test_fault_configuration_requires_typed_values(self):
        for values in ({"write_mode": "partial"}, {"feedback_mode": "follow"},
                       {"cancel_honored": 1}, {"release_honored": None}, {"release_lies": "yes"}):
            with self.subTest(values=values), self.assertRaises(TypeError):
                Faults(**values)
        with self.assertRaises(TypeError):
            SimTnc(faults={})
        with self.assertRaises(TypeError):
            SimTnc().set_faults({})

    def test_snapshots_and_faults_are_immutable(self):
        sim = SimTnc()
        with self.assertRaises(FrozenInstanceError):
            sim.snapshot().ptt_line = True
        with self.assertRaises(FrozenInstanceError):
            sim.faults.release_honored = False

    def test_owner_validation_and_single_attachment(self):
        for owner in (None, 1, b"controller"):
            with self.subTest(owner=owner), self.assertRaises(TypeError):
                SimTnc().attach(owner)
        for owner in ("", "  ", "a" * 129):
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                SimTnc().attach(owner)
        sim = prepared()
        with self.assertRaises(RuntimeError):
            sim.attach("controller")


class TimingTests(unittest.TestCase):
    def test_queue_key_up_and_completion_boundaries(self):
        sim = prepared(queue_delay_ms=100, ptt_duration_ms=300)
        sim.write("controller", b"packet", 0)
        self.assertTrue(sim.snapshot().queued)
        self.assertFalse(sim.snapshot().ptt_line)
        self.assertFalse(sim.advance(99).ptt_line)
        self.assertTrue(sim.advance(100).ptt_line)
        self.assertEqual(sim.snapshot().keyed_mono_ms, 100)
        self.assertTrue(sim.advance(399).ptt_line)
        final = sim.advance(400)
        self.assertFalse(final.ptt_line)
        self.assertFalse(final.queued)
        self.assertEqual(final.writes_accepted, 1)

    def test_zero_delay_still_requires_processing_the_new_queue(self):
        sim = prepared(queue_delay_ms=0, ptt_duration_ms=10)
        sim.write("controller", b"packet", 0)
        self.assertFalse(sim.snapshot().ptt_line)
        self.assertTrue(sim.advance(0).ptt_line)
        self.assertFalse(sim.advance(10).ptt_line)

    def test_coarse_time_step_settles_an_entire_completed_pulse(self):
        sim = prepared(queue_delay_ms=100, ptt_duration_ms=300)
        sim.write("controller", b"packet", 0)
        final = sim.advance(2000)
        self.assertFalse(final.ptt_line)
        self.assertFalse(final.queued)
        self.assertEqual(final.feedback, "off")

    def test_coarse_and_fine_sampling_agree_on_final_state(self):
        for delay in (0, 7, 100):
            for duration in (1, 20):
                for sense_delay in (0, 15):
                    for end in sorted({0, delay, delay + duration - 1, delay + duration, delay + duration + 30}):
                        args = dict(queue_delay_ms=delay, ptt_duration_ms=duration, feedback_delay_ms=sense_delay)
                        coarse, fine = prepared(**args), prepared(**args)
                        coarse.write("controller", b"packet", 0)
                        fine.write("controller", b"packet", 0)
                        for stamp in range(end + 1):
                            fine.advance(stamp)
                        with self.subTest(args=args, end=end):
                            self.assertEqual(coarse.advance(end), fine.snapshot())

    def test_clock_rejects_backwards_and_noninteger_input_without_mutation(self):
        sim = prepared()
        sim.advance(10)
        before = sim.snapshot()
        for stamp in (9, -1):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                sim.advance(stamp)
            self.assertEqual(sim.snapshot(), before)
        for stamp in (True, None, 10.5, "11"):
            with self.subTest(stamp=stamp), self.assertRaises(TypeError):
                sim.advance(stamp)
            self.assertEqual(sim.snapshot(), before)

    def test_equal_timestamps_are_allowed(self):
        sim = prepared()
        self.assertEqual(sim.advance(10), sim.advance(10))

    def test_later_write_settles_previous_transmission(self):
        sim = prepared(queue_delay_ms=10, ptt_duration_ms=10)
        sim.write("controller", b"first", 0)
        sim.write("controller", b"second", 30)
        self.assertEqual(sim.snapshot().writes_accepted, 2)
        self.assertEqual(sim.snapshot().queued_mono_ms, 30)
        self.assertFalse(sim.snapshot().ptt_line)


class QueueTests(unittest.TestCase):
    def test_write_requires_attached_matching_owner(self):
        sim = SimTnc()
        with self.assertRaises(RuntimeError):
            sim.write("controller", b"packet", 0)
        self.assertFalse(sim.snapshot().queued)
        self.assertTrue(sim.snapshot().contention_seen)
        with self.assertRaises(TypeError):
            sim.write(None, b"packet", 0)

    def test_second_writer_cannot_overwrite_pending_data(self):
        sim = prepared(queue_delay_ms=100)
        sim.write("controller", b"first packet", 0)
        with self.assertRaises(RuntimeError):
            sim.write("other-controller", b"other", 1)
        self.assertEqual(sim.snapshot().payload_bytes, len(b"first packet"))
        self.assertEqual(sim.snapshot().writes_accepted, 1)
        self.assertTrue(sim.snapshot().contention_seen)

    def test_queue_has_single_frame_capacity(self):
        sim = prepared(queue_delay_ms=100)
        sim.write("controller", b"first", 0)
        with self.assertRaises(RuntimeError):
            sim.write("controller", b"second", 1)
        self.assertEqual(sim.snapshot().payload_bytes, 5)
        self.assertEqual(sim.snapshot().writes_accepted, 1)

    def test_payload_size_and_type_are_checked_before_queueing(self):
        sim = prepared(max_payload_bytes=4)
        for payload in (b"", b"12345"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                sim.write("controller", payload, 0)
        for payload in ("123", 1000000, None, [1, 2]):
            with self.subTest(payload=payload), self.assertRaises(TypeError):
                sim.write("controller", payload, 0)
        self.assertFalse(sim.snapshot().queued)
        sim.write("controller", b"1234", 0)
        self.assertEqual(sim.snapshot().payload_bytes, 4)

    def test_mutable_payload_is_copied(self):
        payload = bytearray(b"packet")
        sim = prepared()
        sim.write("controller", payload, 0)
        payload.clear()
        self.assertEqual(sim.snapshot().payload_bytes, 6)

    def test_failed_down_and_occupied_writes_accept_nothing(self):
        for mode, error in ((WriteMode.DOWN, ConnectionError), (WriteMode.FAILED, ConnectionError),
                            (WriteMode.OCCUPIED, RuntimeError)):
            sim = prepared(faults=Faults(write_mode=mode))
            with self.subTest(mode=mode), self.assertRaises(error):
                sim.write("controller", b"packet", 0)
            self.assertFalse(sim.snapshot().queued)
            self.assertEqual(sim.snapshot().writes_accepted, 0)

    def test_partial_write_retains_prefix_and_reports_short_count(self):
        sim = prepared(faults=Faults(write_mode=WriteMode.PARTIAL))
        with self.assertRaises(PartialWriteError) as caught:
            sim.write("controller", b"packet", 0)
        self.assertEqual(caught.exception.accepted_bytes, 1)
        self.assertEqual(caught.exception.requested_bytes, 6)
        self.assertTrue(sim.snapshot().queued)
        self.assertTrue(sim.snapshot().partial)
        self.assertEqual(sim.snapshot().payload_bytes, 1)
        self.assertEqual(sim.snapshot().writes_accepted, 0)

    def test_partial_write_prefix_can_key_if_not_cancelled(self):
        sim = prepared(queue_delay_ms=100, faults=Faults(write_mode=WriteMode.PARTIAL))
        with self.assertRaises(PartialWriteError):
            sim.write("controller", b"packet", 0)
        self.assertTrue(sim.advance(100).ptt_line)

    def test_partial_fault_requires_a_multibyte_payload(self):
        sim = prepared(faults=Faults(write_mode=WriteMode.PARTIAL))
        with self.assertRaises(ValueError):
            sim.write("controller", b"x", 0)
        self.assertFalse(sim.snapshot().queued)


class CancellationAndReleaseTests(unittest.TestCase):
    def test_owner_can_cancel_pending_full_or_partial_write(self):
        for mode in (WriteMode.NORMAL, WriteMode.PARTIAL):
            sim = prepared(queue_delay_ms=100, faults=Faults(write_mode=mode))
            try:
                sim.write("controller", b"packet", 0)
            except PartialWriteError:
                pass
            self.assertFalse(sim.cancel("other-controller"))
            self.assertTrue(sim.cancel("controller"))
            self.assertFalse(sim.advance(100).ptt_line)
            self.assertFalse(sim.snapshot().queued)

    def test_ignored_cancel_can_be_followed_by_key_up(self):
        sim = prepared(queue_delay_ms=100, faults=Faults(cancel_honored=False))
        sim.write("controller", b"packet", 0)
        self.assertFalse(sim.cancel("controller"))
        self.assertTrue(sim.advance(100).ptt_line)

    def test_cancel_cannot_unkey_an_active_transmission(self):
        sim = prepared()
        sim.write("controller", b"packet", 0)
        sim.advance(0)
        self.assertFalse(sim.cancel("controller"))
        self.assertTrue(sim.snapshot().ptt_line)

    def test_honored_release_clears_line_and_queue(self):
        sim = prepared()
        sim.write("controller", b"packet", 0)
        sim.advance(0)
        self.assertTrue(sim.force_off())
        self.assertFalse(sim.snapshot().ptt_line)
        self.assertFalse(sim.snapshot().queued)

    def test_stuck_ptt_survives_deadline_and_release_command(self):
        sim = prepared(ptt_duration_ms=100, faults=Faults(release_honored=False))
        sim.write("controller", b"packet", 0)
        sim.advance(0)
        self.assertTrue(sim.advance(10000).ptt_line)
        self.assertFalse(sim.force_off())
        self.assertTrue(sim.snapshot().ptt_line)

    def test_successful_release_ack_can_leave_line_on(self):
        sim = prepared(faults=Faults(release_lies=True))
        sim.write("controller", b"packet", 0)
        sim.advance(0)
        self.assertTrue(sim.force_off())
        self.assertTrue(sim.snapshot().ptt_line)
        self.assertEqual(sim.snapshot().feedback, "on")

    def test_faults_can_be_changed_without_advancing_time(self):
        sim = prepared(ptt_duration_ms=10, faults=Faults(release_honored=False))
        sim.write("controller", b"packet", 0)
        sim.advance(100)
        self.assertTrue(sim.snapshot().ptt_line)
        changed = sim.set_faults(Faults())
        self.assertEqual(changed.mono_ms, 100)
        self.assertTrue(changed.ptt_line)
        self.assertFalse(sim.advance(100).ptt_line)


class CrashAndFeedbackTests(unittest.TestCase):
    def test_crash_after_key_up_latches_model_line(self):
        sim = prepared()
        sim.write("controller", b"packet", 0)
        sim.advance(0)
        sim.crash()
        self.assertTrue(sim.advance(10000).ptt_line)
        self.assertFalse(sim.force_off())
        self.assertFalse(sim.cancel("controller"))
        with self.assertRaises(ConnectionError):
            sim.write("controller", b"packet", 10000)

    def test_crash_before_key_up_freezes_pending_queue(self):
        sim = prepared(queue_delay_ms=100)
        sim.write("controller", b"packet", 0)
        sim.crash()
        state = sim.advance(1000)
        self.assertFalse(state.alive)
        self.assertFalse(state.ptt_line)
        self.assertTrue(state.queued)
        self.assertFalse(sim.cancel("controller"))

    def test_feedback_delay_is_separate_from_line_state(self):
        sim = prepared(queue_delay_ms=100, ptt_duration_ms=300, feedback_delay_ms=50)
        sim.write("controller", b"packet", 0)
        self.assertTrue(sim.advance(100).ptt_line)
        self.assertEqual(sim.snapshot().feedback, "off")
        self.assertEqual(sim.advance(149).feedback, "off")
        self.assertEqual(sim.advance(150).feedback, "on")
        self.assertEqual(sim.advance(400).feedback, "off")

    def test_short_pulse_can_complete_before_delayed_feedback_turns_on(self):
        sim = prepared(ptt_duration_ms=10, feedback_delay_ms=20)
        sim.write("controller", b"packet", 0)
        self.assertTrue(sim.advance(0).ptt_line)
        self.assertEqual(sim.snapshot().feedback, "off")
        self.assertFalse(sim.advance(10).ptt_line)
        self.assertEqual(sim.snapshot().feedback, "off")

    def test_lost_and_false_feedback_do_not_change_the_line(self):
        for mode, expected in ((FeedbackMode.UNAVAILABLE, "lost"),
                               (FeedbackMode.FALSE_OFF, "off"), (FeedbackMode.FALSE_ON, "on")):
            sim = prepared(faults=Faults(feedback_mode=mode))
            sim.write("controller", b"packet", 0)
            state = sim.advance(0)
            with self.subTest(mode=mode):
                self.assertTrue(state.ptt_line)
                self.assertEqual(state.feedback, expected)

    def test_false_on_feedback_can_persist_after_successful_release(self):
        sim = prepared(faults=Faults(feedback_mode=FeedbackMode.FALSE_ON))
        sim.write("controller", b"packet", 0)
        sim.advance(0)
        self.assertTrue(sim.force_off())
        self.assertFalse(sim.snapshot().ptt_line)
        self.assertEqual(sim.snapshot().feedback, "on")


if __name__ == "__main__":
    unittest.main()
