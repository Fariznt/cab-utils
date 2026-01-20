# CAB Utils

A hub of course registration utilities for Brown University developed as a Django monolith with a simple frontend running asynchronous services. 

## Overview

This web app is intended as a collection of utilities brought together under one hub. Currently, development has only reached links to existing utilities (ex. Critical Review for course reviews), one unique utility (Seat Signal), and some incomplete concepts (visualization of course prerequisite relations, course offering trends, stronger course search engine).

In general, this web app was developed by reverse-engineering Brown University's API and database conventions used for the [course registration site](https://cab.brown.edu/) by observing the network calls that occur during course interaction. For example, core/management/commands provides a update_db command that interacts with the API to build a local database of courses, opening up a myriad of possibilities for flexible querying, analyses, and other utilities.

---

# Utilities
(Links to sites I didn't make but are connected to CAB Utils are not included here)

## Seat signal

The primary utility that is done being implemented and not seen elsewhere is Seat Signal, an application that allows you to track multiple classes and receive a direct call when a seat opens up. This solves a common problem on campus, and does so greater than its competitor (Coursicle) by
a. Allowing tracking of 5 instead of only 1 class for free (or very cheap, if you run the webapp yourself)
b. Sending a call with an informative voice message, instead of a mere notification which is easy to miss

Seat signal works by letting users add courses through their account, and running an asynchronous polling of the C@B API for seat count, and using [Twilio](https://www.twilio.com/docs) to send a call when a seat opens up for any user.

## Prereq Map

A course prerequisite visualizer. Queries course descriptions and uses string parsing to infer course dependencies (the C@B API simply does not provide this directly). Then, visualizes these dependencies in a tree.

This is not yet offerred in the web app, but the core backend software that GETs all course descriptions in a given semester from C@B and parses the course description strings for likely dependencies is complete [here](https://github.com/Fariznt/CAB_Prerequisites).

---

# Roadmap before launch

This web app is functional, and has been deployed on a VPS previously for testing. Anyone is welcome to pull and run it themselves. In fact, I've run it in dev to use its utility myself already. Before launching as a webapp for wider use, there's some work that is absolutely necessary:

- Password hashing / phone number encryption and other security features
- Get the Twilio number currently in use for this webapp verified
    - This type of calling gets callers labeled as Scam Likely, and steps need to be taken to ensure call reputation and prevent mobile carrier blocking
- Homepage text (mostly user-friendly version of REAMDE stuff)

# I want to run my own. What do I do?
1. You need .env in the root directory with Twilio credentials (after making an account and paying for some credits) and the cap on the number of Seat Signals (courses being watched for new seats) permitted:
- ACCOUNT_SID
- AUTH_TOKEN
- FROM_NUMBER
- SIGNAL_CAP

2. Install dependencies in requirements.txt
- `pip install -r requirements.txt`

To run in dev:
- `python manage.py runserver` to start the local web server
- `python manage.py update_db --help` to learn how to create your local C@B database
- `python manage.py enable_ss` to start running the asynchronous polling service for Seat Signal





# Possible Improvements

Improvements (not absolutely necessary, but imporant for scale):
- [voIP.ms](https://voip.ms/) for texting functionality, including scheduling and canceling Seat Signal by text (Twilio is too expensive for free hosting)
- Client-side phone number validation, enforcing uniqueness, "forgot my password" functionality
- Call throttling
- Switch to [Telnyx](https://developers.telnyx.com/docs/overview) for reduced per-second cost (Twilio charges per minute)
- Code quality improvements (better API conventions, CSS)

Features:
- Use graphviz or similar to finish implementing PreReq map
- Providing a stronger course search engine than C@B is a big undertaking---provide the ability for devs to directly query the database instead
