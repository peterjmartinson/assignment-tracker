# assignment-tracker
Pipeline orchestrator for student assignments. Ingests raw Classroom email JSON from dispatch, parses student identity and due dates, and routes cards to Trello via its REST API. Architecture scales to generate and sync custom summer math, French, and Latin tasks with screamsheet. Lean, TDD-backed, running locally on a Linux daemon.
