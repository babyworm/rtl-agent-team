"""Reproducible generated inputs for the simulation verdict contract."""

import os
import random
import string

import pytest

from tests.unit.test_verify_evidence import evidence


@pytest.mark.parametrize('seed', [0, 17, 109])
def test_failure_signals_dominate_completion_and_unrelated_output(seed):
    rng = random.Random(seed)
    case_count = 2000 if os.environ.get('RAT_EXTENDED_CONTRACTS') == '1' else 100
    blockers = [
        ('FAIL: mismatch', 'FAIL'), ('UVM_ERROR : 1', 'FAIL'),
        ('UVM_FATAL : 7', 'FAIL'), ('%Error: assertion', 'FAIL'),
        ('RAT_TIMEOUT: deadline reached', 'TIMEOUT'),
        ('RAT_STALL: no output', 'STALL'), ('RAT_HANG: no progress', 'HANG'),
    ]
    for case in range(case_count):
        newline = rng.choice(['\n', '\r\n'])
        noise = ['tool output ' + ''.join(rng.choices(string.ascii_lowercase + string.digits, k=50))
                 for _ in range(rng.randrange(8))]
        signal, expected = rng.choice(blockers)
        completed = rng.choice(['RAT_SIM_PASS: checks completed', 'ALL TESTS PASSED',
                                'TESTS=3 PASS=3 FAIL=0 SKIP=0'])
        assert evidence.classify(0, newline.join(noise)) == 'INCONCLUSIVE'
        assert evidence.classify(0, newline.join(noise + [completed])) == 'PASS'
        lines = noise + [completed, signal]
        rng.shuffle(lines)
        log = newline.join(lines)
        assert evidence.classify(0, log) == expected, (seed, case, log)
        assert evidence.classify(124, log) == 'TIMEOUT', (seed, case, log)
        assert evidence.classify(rng.randrange(1, 124), completed) == 'FAIL', (seed, case, completed)
