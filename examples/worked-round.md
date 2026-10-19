# Worked example: one peer-evaluation round

Team of 3 on a deliverable set worth 32 points; the team earned 27.
One student (Dev Rao) never submitted a ballot. Input is deliberately messy:
mixed separators, a bare NAU id without the domain.

## What students typed

**Alvarez, Bea** typed into the allocation question:

```
abc12@nau.edu = 110
cpo59@nau.edu = 100
dmr7@nau.edu = 90
```

parsed: `{'abc12@nau.edu': 110, 'cpo59@nau.edu': 100, 'dmr7@nau.edu': 90}` — total 300/300, valid: True

**Okonkwo, Chi** typed into the allocation question:

```
abc12@nau.edu: 108
cpo59 = 104
dmr7@nau.edu - 88
```

parsed: `{'abc12@nau.edu': 108, 'cpo59@nau.edu': 104, 'dmr7@nau.edu': 88}` — total 300/300, valid: True

## What the script computes

| Student | Ratings received | Mean | Factor | Adjustment posted |
|---|---|---|---|---|
| Alvarez, Bea | 2 | 109.0 | 1.09 | **+2.43** |
| Okonkwo, Chi | 2 | 102.0 | 1.02 | **+0.54** |
| Rao, Dev | 2 | 89.0 | 0.89 | **-2.97** |

Team grade stays **27 / 32** for everyone — the adjustment is a separate
0-point line item, so the group's denominator never changes.

Flags raised for the instructor:

- **Rao, Dev**: did_not_submit_evaluation

## The comment each student receives

Posted automatically onto the adjustment assignment, names stripped:

### Alvarez, Bea

```
============================================================
PEER REVIEW REPORT
Tangible Board Game -- Draft
Student: Alvarez, Bea
------------------------------------------------------------
Ratings received: 2 (including your own self-rating)
Mean rating      : 109.0
Factor           : 1.09
------------------------------------------------------------
Team earned 27 of 32 on the covered deliverables.
27 x 1.09 = 29.43
ADJUSTMENT POSTED: +2.43
------------------------------------------------------------
WHAT YOUR TEAMMATES SAID YOU DID WELL:
  - built the whole card deck
------------------------------------------------------------
AREAS FOR IMPROVEMENT:
  (none)
============================================================
```

### Okonkwo, Chi

```
============================================================
PEER REVIEW REPORT
Tangible Board Game -- Draft
Student: Okonkwo, Chi
------------------------------------------------------------
Ratings received: 2 (including your own self-rating)
Mean rating      : 102.0
Factor           : 1.02
------------------------------------------------------------
Team earned 27 of 32 on the covered deliverables.
27 x 1.02 = 27.54
ADJUSTMENT POSTED: +0.54
------------------------------------------------------------
WHAT YOUR TEAMMATES SAID YOU DID WELL:
  - kept the rules doc current
------------------------------------------------------------
AREAS FOR IMPROVEMENT:
  (none)
============================================================
```

### Rao, Dev

```
============================================================
PEER REVIEW REPORT
Tangible Board Game -- Draft
Student: Rao, Dev
------------------------------------------------------------
Ratings received: 2 (you did not submit an evaluation, so your own rating is not among them)
Mean rating      : 89.0
Factor           : 0.89
------------------------------------------------------------
Team earned 27 of 32 on the covered deliverables.
27 x 0.89 = 24.03
ADJUSTMENT POSTED: -2.97
------------------------------------------------------------
WHAT YOUR TEAMMATES SAID YOU DID WELL:
  - good ideas in week 1
------------------------------------------------------------
AREAS FOR IMPROVEMENT:
  - missed the second build session
  - went quiet after the prototype
============================================================
```
