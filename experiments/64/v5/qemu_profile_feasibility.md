# Existing disposable guest: accessible target, pending latency enrollment

Source inspected: Fishhat main `f96b83dc20f059d62a4363a63c37bb0ef8c642e5`. This is a read-only feasibility handoff, not a new profile approval, consumer change or launched campaign.

## Access is available; the shared measurement is missing

[The `native-controller` job](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/.github/workflows/ci.yml) runs on ordinary `ubuntu-24.04` GitHub-hosted workers. It checks out source, installs the locked workspace, downloads its same-run installed-wheel artifact and invokes:

```sh
uv run --locked --all-packages --group dev --python 3.12 \
  python -m scripts.native_linux_enrollment --github-hosted-only \
  --output artifacts/native-fixture/controller-enrollment.json
```

The workflow contains no configured private secret or external machine for this facility. Guest SSH keys are generated for each disposable session, the listener is loopback-only, and its private QMP endpoint and root/control/data images are owned temporary resources. Public artifact/package availability remains an ordinary execution dependency, not a missing private-access credential.

The existing entrypoint explicitly requires a real GitHub-hosted Ubuntu 24.04 main-branch push or workflow-dispatch context. Preserve that guard; do not spoof environment variables to run the existing enrollment on a disallowed branch. An independently approved shared workflow/stage can reuse the facility at its authorized scope. The current full command has no common-collector hook and destroys the guest before returning, so a later shell step cannot attach to a surviving target.

## Exact source and useful lifecycle seam

| File | Existing mechanism |
| --- | --- |
| [native_linux_enrollment.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/scripts/native_linux_enrollment.py) | `enroll()` checks the disposable-main-runner scope. `provision()` pins QEMU. `admitted_guest_controller()` owns/attests the controller. `boot_guest()` nests the guest and controller lifetime, waits for authenticated readiness, establishes actual storage, performs installed checkpoint qualification and later tears down all resources. |
| [native_linux_images.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/scripts/native_linux_images.py) | `guest_inputs()` authenticates the public base image and creates exact owned QCOW2 root/control/data inputs. Root has the pinned read-only base backing; control/data are independent image files. |
| [native_linux_guest.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/scripts/native_linux_guest.py) | `guest_session()` creates and cleans private keys/configuration. `Guest.launch()` fixes QEMU resources. `ready()` establishes boot/enrollment/account identity. `guarded()` executes an argument vector only after checking the enrolled current boot, process and endpoint. `ssh(..., input_path=...)` supports input delivery through the existing guarded path. |
| [native_linux_storage.py](https://github.com/nashspence/fishhat/blob/f96b83dc20f059d62a4363a63c37bb0ef8c642e5/scripts/native_linux_storage.py) | `qualify_storage()` validates exact owned guest device serials/identities, formats only the owned control/data disks, mounts control as ext4 and data as XFS with project quotas, establishes permissions/canaries and independently observes mount/device identity. |

The concrete seam is **inside** `guest_session()` and `admitted_guest_controller()`, after authenticated `guest.ready()` and successful `qualify_storage()`, before either context exits. In the full existing `boot_guest()` this is immediately after `report["storage"]` succeeds and before `qualify_checkpoint()`. A shared qualification packet can reuse the required fixture primitives for this bounded resource purpose; it does not need to replay unrelated owner-installation/exhaustion/restore proof matrices solely to get three timings. It must not claim those omitted product proofs were rerun.

Deliver a hash-pinned shared collector through the current authenticated transfer/command path and execute it **inside the guest** against the actual admitted filesystem. Retain its in-guest outer clock observations, original result bytes and before/after boot/mount/resource facts; transport/setup costs are separate. Host-side SSH response time and a host-directory preflight cannot qualify a guest operation. Collect and verify the report before the existing owned cleanup runs. For actual Fishhat checkpoint acceptance, retain the protected installed runtime/wheel/context requirements and existing independent native evidence; generic resource qualification alone does not replace them.

This describes a required new bounded shared integration stage, not an already callable common-collector mode. Reuse the facility through an approved scope rather than monkeypatching its main guard, qualification results or cleanup.

## Actual resource and storage scope

`Guest.launch()` fixes QEMU `pc-q35-8.2`, `-accel tcg,thread=multi`, `-cpu max`, `-m 2048M`, and `-smp 2`. It supplies owned QCOW2 files through `virtio-blk-pci`. The launch arguments do **not** select an explicit cache mode. Record the actual QEMU/default/backing semantics; do not assume direct I/O, write-through hardware or physical persistence.

TCG is deliberate. The initial selection [#138](https://github.com/nashspence/fishhat/issues/138#issuecomment-6727047279) avoids assuming nested KVM availability, and `controller_channel()` actively rejects `query-kvm.enabled != false`. There is no current KVM option to turn on within the qualified profile. An accelerated profile would be a separately selected and qualified environment, not an unnoticed speed switch.

The current common public profile requires four CPUs, 14 GiB and probe Python 3.11.9. This guest cannot pass those resource requirements. The selected installed owner runtime is Python 3.12.16; the collector's actual interpreter must also be explicit. A new **general 2-vCPU/2-GiB TCG guest profile** needs its own fixed admission conditions/campaign. Do not reuse the public profile ID, normalize time to pretend the resources match, or infer bare-metal timings from emulated timings.

Its valid failure claim can be scoped to the tested guest/process/storage domain while the host/backing remains intact. Graceful guest reboot and process/storage interruption prerequisites already have recorded evidence. Stronger abrupt guest-crash behavior requires its own applicable witness; physical host-power survival is not supplied by a healthy guest filesystem over the relaxed public-worker root. This policy need not require that stronger claim when the consumer does not make it.

## Actual observed facility costs

The accepted [fresh-main run 45156202495](https://github.com/nashspence/fishhat/actions/runs/45156202495) and [native-controller job 137636936890](https://github.com/nashspence/fishhat/actions/runs/45156202495/job/137636936890) completed successfully on 2026-11-23. The GitHub job/step timestamps and original decoded stage logs show:

| Scope | Observed wall time |
| --- | ---: |
| Whole native-controller job | 5,031 seconds (83m 51s) |
| Full enrollment command | 4,976 seconds (82m 56s) |
| First guest boot/readiness | 128.386714 seconds |
| First guest refusal checks | 25.534890 seconds |
| Successful control/data storage setup | 26.294009 seconds |
| Graceful guest reboot stage | 124.964012 seconds |
| Installed protected checkpoint witness stage | 779.874863 seconds |

These are fixture/correctness/observer stage times, **not checkpoint operation latencies**. The full command includes installation, several other prerequisites, snapshots/restores and separate fault sessions. It is inappropriate to reproduce the entire 83-minute campaign merely for a recurring small performance gate. The narrow setup cost must be measured rather than inferred by summing overlapping stages.

## Recommended finite next step

Run one narrow, explicitly scoped shared resource experiment through the existing owned guest lifecycle: capture actual mount/backing/runtime identity; run the unchanged native-storage operation shapes with all required synchronization; retain three complete raw observations and every failure; preserve one appropriate already-required guest continuity witness; verify output and complete cleanup. This asks shared infrastructure for code/evidence, not project design for a calibrator or an external machine.

The guest is useful to investigate because it is reproducible, supports real guest filesystem semantics and has an existing custody/failure-evidence path. It is **not yet demonstrated to be performance-meaningful for a tight budget**. TCG and the host-backed images may introduce large costs or tails. If it meets useful independently approved raw budgets, enroll that exact scoped profile. If it does not, retain the result and do not translate it into a native-hardware pass or automatically widen a budget. That concrete evidence should drive the next resource choice; missing approval or measurement is not missing access.

The earlier 100/150 ms public-storage screens do not establish that every useful budget will fail. They test those specific fixed windows. Storage failure guarantees and timing acceptance require distinct evidence; changing either claim cannot erase the recorded result for the other.
