---
title: My Document
author: 
- Firstname Lastname
---

# Background

!!! note 
    Standard MkDocs/Python Markdown admonitions work

??? info
    Collapsable admonitions work too

You can generate embed graphics using latex (assumed to be tikz), and provide an alt-text for accessibility. 

``` latex {alt="Drawing of a circle"}
\begin{tikzpicture}
    \draw (0,0) circle (1cm);
\end{tikzpicture}
```

# Slideshows

!!! frame "Frame Title"

    Frame contents go here

    !!! pause
        Displayed when advanced
    
!!! exercise
    You can put exercises between frames

??? answer
    And you can put answers too. 

    Answers are **excluded** from handout mode

!!! frame
    You can put the next frame here

!!! page 

    ## Sample Worksheet 
    
    You can also make a worksheet with spaces

    !!! exercise 
        A first problem

    ??? answer
        Answer to first question

    !!! vfill

    !!! exercise
        Another exercise

    ??? answer
        Answer to second question
    
    !!! vfill

    !!! newpage

    !!! exercise

        Exercise on next page

!!! page 

    ## Gradescope Worksheet

    Assignment: 

    Name: 

    1. heres a question

    !!! vfillbox

    2. here's another

    !!! vfillbox

    3. Here's a third

    !!! vfillbox


# Mathematics environments

!!! definition 
    Definitions work

!!! theorem
    Theorems too

Currently supported environments are hardcoded into the template, particularly for latex output.
Eventually there should be a more dynamic solution. 