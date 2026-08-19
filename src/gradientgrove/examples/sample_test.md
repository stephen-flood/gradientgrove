---
title: Question Test
author: Stephen Flood
date: August 19, 2026
---

!!! maketitle

This document tests question numbering, nested parts/subparts, point
accumulation, and the grading table.

!!! exam

    !!! gradetable

    This document tests question numbering, nested parts/subparts, point
    accumulation, and the grading table.

    !!! question "5"
        A simple question with points assigned directly to the question.

        Compute \(2+2\).

    !!! newpage

    !!! question
        This question gets its points entirely from its parts.

        !!! question "3"
            Part (a) is worth 3 points.

            Compute \(1+1\).

        !!! vfill

        !!! question "4"
            Part (b) is worth 4 points.

            Compute \(2+2\).

        !!! vfillbox

    !!! newpage 

    !!! question
        This question gets its points from parts, one of which gets its
        points from subparts.

        !!! question "2"
            This part is worth 2 points directly.

        !!! question
            This part has no point value of its own.

            !!! question "3"
                First subpart: 3 points.

            !!! question "4"
                Second subpart: 4 points.

    !!! newpage 

    !!! question "10"
        This question explicitly says 10 points.

        Its nested parts have point values too, but the explicit 10-point
        value on the parent should override the accumulated value below.

        !!! question "2"
            First part.

        !!! question "3"
            Second part.

    !!! question
        This question and all of its children have no assigned points.

        !!! question
            An unscored part.

        !!! question
            Another unscored part.

    !!! question "5"

    !!! question "5"

    !!! question "5"

    !!! question "5"

    !!! question "5"

    !!! question "5"

    !!! question "5"

    !!! question "5"

    !!! question "5"


