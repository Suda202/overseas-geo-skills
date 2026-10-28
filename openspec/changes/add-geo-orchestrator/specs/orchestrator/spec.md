# Orchestrator capability

## ADDED Requirements

### Requirement: submit a case and receive a question bank

The platform SHALL accept a presales case and return the question-bank JSON
produced by the Dify workflow, without the caller interacting with Dify.

#### Scenario: valid case returns an artifact

- **WHEN** a valid case is submitted with the KeepBalance test values
- **THEN** the run completes and the artifact contains `questions`,
  `bank_config`, `schema_version` and `question_count`
- **AND** `question_count` equals the length of `questions`

#### Scenario: artifact matches the Dify run output

- **GIVEN** a completed run whose Dify execution id is known
- **WHEN** the artifact is compared against that execution's outputs in Dify
- **THEN** the question texts and count are identical

### Requirement: dual input channel

The platform SHALL accept a case as a form submission, as a JSON body, or as a
single pasted JSON document, and SHALL validate all three into one `CaseInput`
model before calling Dify.

#### Scenario: form and JSON inputs are equivalent

- **GIVEN** a valid case submitted through the form
- **AND** the same case submitted as a JSON body
- **WHEN** both are validated
- **THEN** both yield equal `CaseInput` instances
- **AND** both produce equal Dify `inputs` objects

#### Scenario: tolerant paste parse

- **GIVEN** pasted text wrapped in a markdown code fence, containing smart
  quotes and a trailing comma inside the competitors array
- **WHEN** submitted to the paste endpoint
- **THEN** the case is accepted and validated

#### Scenario: flat paste is accepted

- **GIVEN** pasted JSON that is a bare flat object with no `case` wrapper
- **WHEN** submitted to the paste endpoint
- **THEN** it is accepted as a case

#### Scenario: malformed field is named

- **GIVEN** a case whose `competitors` is `"By-Health, Swisse"`
- **WHEN** validated
- **THEN** the error names `competitors` and quotes the offending value

### Requirement: request shape mirrors the workflow

The Dify `inputs` object SHALL be built from `CaseInput` field names that match
the workflow's start-node variable names exactly, with `competitors` serialized
as a JSON array string.

#### Scenario: no field renaming

- **WHEN** `to_inputs()` is called on a valid case
- **THEN** the resulting keys are exactly `brand_name`, `company_name`,
  `business_mode`, `category`, `official_domain`, `topics`, `competitors`,
  `regions`, `supplemental`
- **AND** `competitors` is a JSON string parseable as a list of objects with
  `name` and `official_domain`

### Requirement: run records are inspectable

Every run SHALL persist its input, Dify's raw response, and the extracted
artifact under `runs/<run_id>/`, and these records SHALL remain readable after a
platform restart.

#### Scenario: artifact served from disk after restart

- **GIVEN** a completed run with id `R`
- **WHEN** the platform restarts and `GET /api/v1/runs/R/artifact` is called
- **THEN** the artifact is returned from disk without calling Dify

#### Scenario: failed run is recorded with its cause

- **GIVEN** a run in which Dify returned `status: failed`
- **WHEN** the run record is read
- **THEN** `error.json` contains Dify's own error message verbatim

### Requirement: failure is loud

The platform MUST NOT serve an artifact for a run whose Dify execution failed or
whose `validate_valid` output is false. It SHALL return an error identifying
which condition held.

#### Scenario: validation failure is refused

- **GIVEN** a run whose Dify outputs carry `validate_valid: false`
- **WHEN** `GET /runs/{id}/artifact` is called
- **THEN** the response is 409
- **AND** the body carries `validate_first_errors`

#### Scenario: Dify execution failure is refused

- **GIVEN** a run whose Dify response has `status: failed`
- **WHEN** the artifact is requested
- **THEN** the response is 422
- **AND** the body carries Dify's error message

### Requirement: configuration is explicit

The Dify base URL, API key and timeout SHALL come from environment variables,
with the base URL defaulting to `http://dify.ads.qihoo.net/v1`. The service
SHALL refuse to start a run without a key, and `/healthz` SHALL report whether
the key is accepted.

#### Scenario: missing key blocks runs

- **GIVEN** no `DIFY_API_KEY` in the environment
- **WHEN** a run is submitted
- **THEN** the response is 503 naming the missing variable
- **AND** no request is sent to Dify

#### Scenario: healthz reports auth state

- **WHEN** `GET /healthz` is called
- **THEN** the body reports `dify_reachable` and `auth_ok` separately
