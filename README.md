# TraceHound

HW #6 implements a read-only `query_metrics()` slice with a permission gate, explicit human approval, and a JSON audit record for each request.

From the repository root, run the allowed/refused demonstration with Python 3.11 or later.

```sh
python3 -B -m agent.hw6_slice
```

Run the six tests.

```sh
python3 -B -m unittest discover -s tests -v
```

The backend, metric values, permissions, and approvals are simulated. The demonstration emits two audit records and two result records. The captured run is in `logs/hw6_run.txt`.

A future Prometheus adapter can replace `fake_monitoring` through the `backend` argument of `query_metrics()`. Keep the gate in front of the adapter and map the allowlisted service and metric to fixed, bounded Prometheus queries executed with a read-only service identity.
