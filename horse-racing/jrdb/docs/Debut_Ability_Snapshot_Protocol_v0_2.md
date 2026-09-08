# Debut Ability Snapshot Protocol v0.2

## Status

**PRE-MODEL STRUCTURAL PROTOCOL — FROZEN BEFORE DEBUT PREDICTIVE COMPARISON**

This protocol supersedes `Debut_Ability_Snapshot_Protocol_v0_1.md` for new Debut/no-scored-history Ability development runs.

The semantic change is narrow and evidence-driven: Issue #332 established that the UKC archive whose data date equals the target race date is available before racing. The accepted implementation evidence in Issues #333/#334/#335 therefore becomes the canonical v0.2 profile-availability contract.

No Debut predictive model, hyperparameter, or 2024-2025 predictive metric is selected or inspected by this protocol.

## 1. Target population and target label

Debut target:

```text
career_scored_run_count = 0
```

This includes both true first starts and runners with prior starts but no valid scored official RunPerf.

Future evaluation target:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

The target result is evaluation-only and must remain physically/logically separate from pre-race features.

## 2. Chronology contract

For target race date D:

```text
target UKC identity/profile: latest valid observation with data_date <= D
historical debut labels:     race_date < D only
current workout/training:    target CHA/CYB PRE_RACE row only
current jockey/trainer:      target KYI PRE_RACE row only
current carried weight:      target KYI PRE_RACE row only
current target result:       forbidden as input
same-day race results:       forbidden as historical input
```

The UKC observation is identity/profile information, not a race result. Issue #332 is the Controller availability evidence authorizing target-date UKC as PRE_RACE input.

Historical result-derived priors remain strict past-only even when same-day UKC profile data is selected.

## 3. UKC profile provenance

Persist at least:

```text
profile_data_date
profile_prior_day_available
profile_same_day_observation_exists
```

Canonical same-day-selection determination is:

```text
profile_same_day_selected := profile_data_date == race_date
```

`profile_data_date` is the selected-source provenance and is authoritative. The derived `profile_same_day_selected` value must be reported/audited explicitly; a duplicate persisted flag is not required unless a later schema version has another consumer need.

Future profile use (`profile_data_date > race_date`) is always forbidden.

## 4. Period policy

- 2010-2012: history formation / warm-up
- 2013-2023: Debut predictive development walk-forward
- 2024-2025: unopened post-freeze temporal confirmation
- 2026 onward: prospective evaluation preferred

The v0.2 structural acceptance run requested by Controller is 2010-2023. No 2024-2025 Debut predictive metric may be queried, calculated, printed, stored, or ranked before a later explicit Controller authorization.

## 5. Snapshot grain and target retention

One row per target runner, keyed by:

```text
race_date
race_key
horse_no
horse_id
```

Valid target runners must not be dropped solely because pedigree, training, or other pre-race evidence is missing.

Missing horse identity is a fail-closed structural violation.

## 6. Pedigree and profile features

Resolve target identity/profile from time-aware UKC using the chronology contract above. Retain sire, broodmare sire, sire line, broodmare-sire line, dam name, birth date, sex, and exact selected profile date when available.

Historical pedigree priors use true first-start official RunPerf labels from dates strictly before D. Retain raw means, sample counts, missing flags, surface-conditioned evidence, and distance-kernel candidates for bandwidths 200/400/600/800m. No shrinkage or bandwidth is selected in this snapshot phase.

## 7. Training/basic PRE_RACE features

Use target CHA/CYB/KYI PRE_RACE fields only. Preserve raw numeric fields and categorical codes without inferring hidden numeric order. Missingness stays explicit.

Persist carried-weight relative value, sex, and pre-race age when derivable from target date plus UKC birth date.

## 8. People prior infrastructure

Persist current jockey/trainer codes and raw strictly-past debut RunPerf summaries with counts/missing flags.

These raw people priors are diagnostics/infrastructure only. Final jockey/trainer effects require a later residualized D2 protocol after the horse/pedigree/training baseline is frozen.

## 9. Result separation and forbidden inputs

Target official RunPerf, if stored alongside the snapshot package, must remain in a separate CURRENT_RESULT table and must not be queried by feature construction.

Forbidden predictors include target/same-day results, target SED final going, odds, popularity, market-derived fields, and any future profile observation.

## 10. Structural audit gates

Fail closed on at least:

- duplicate target key;
- target having a scored official RunPerf strictly before D;
- missing horse identity;
- any historical prior source date >= D;
- current/same-day result leakage;
- future UKC profile use;
- incoherent UKC provenance flags/selected date;
- missing evidence silently encoded as zero;
- non-finite populated numeric prior;
- invalid n/neff/missing relationships;
- market-field contamination.

Report annually and in aggregate: target counts/cohorts, label coverage structurally, profile coverage, prior-day availability, same-day observation and same-day selected rates, pedigree prior coverage/sample distributions, distance-kernel coverage/neff, CHA/CYB coverage, people-prior coverage, weight coverage, and all violations.

## 11. Model-development boundary

This package must not select pedigree shrinkage, distance bandwidth, model family, regularization, categorical encoding vocabulary, or a winning Debut candidate.

After v0.2 structural acceptance on 2010-2023, Controller may freeze a separate Debut Ability comparison protocol. 2024-2025 predictive metrics remain unopened until a later explicit confirmation gate.

## 12. Evidence and supersession

- Issue #329: strict-prior-day snapshot accepted structurally but exposed sparse pedigree coverage.
- Issue #330: 2010-2023 structural coverage confirmed the strict-prior-day limitation.
- Issue #331: coverage reporter smoke PASS.
- Issue #332: `SAME_DAY_UKC_CONFIRMED_PRE_RACE_AVAILABLE`.
- Issue #333: same-day UKC implementation correction accepted.
- Issue #334: canonical same-day snapshot audit accepted.
- Issue #335: 2010-2023 development coverage accepted and sufficient to freeze comparison.

v0.2 formalizes those resolved semantics as the canonical snapshot contract for subsequent Debut development work.
