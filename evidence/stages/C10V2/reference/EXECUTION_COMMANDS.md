# C10/P12 V2 reference execution commands

The resource was provisioned only after explicit user authorization. Secrets,
credential setup, and transient SSH transport commands are intentionally not
recorded here.

## Provisioning shape

```text
gcloud compute instances create bmx-c10v2-qual-20260802
  --project project-a4ddb38c-cbe3-43a7-8d0
  --zone us-west1-b
  --machine-type n2-standard-8
  --min-cpu-platform "Intel Cascade Lake"
  --image-family ubuntu-2404-lts-amd64
  --image-project ubuntu-os-cloud
  --boot-disk-size 50GB
  --boot-disk-type pd-balanced
  --labels stage=c10,purpose=reference-qualification
```

The exact source and AMReX Git bundles, the exact V1 CRLF evidence, the V2
prerun review, and the hash-bound handoff were transferred to the host. The
claim-bearing run was:

```text
bash qualify_c10.sh /home/jherrera2007/c10-work
```

After the qualification and timing outputs had passed, a relative-manifest
working-directory defect stopped only packaging. Existing outcome bytes were
finalized without rerunning them:

```text
bash finalize_reference.sh /home/jherrera2007/c10-work
```

After retrieval and local SHA-256 verification, cleanup was performed with the
equivalent of:

```text
gcloud compute instances delete bmx-c10v2-qual-20260802
  --project project-a4ddb38c-cbe3-43a7-8d0
  --zone us-west1-b
  --delete-disks=all
  --quiet
```

Empty post-delete instance and disk queries are recorded in
`GCE_RESOURCE_LIFECYCLE.json`.
