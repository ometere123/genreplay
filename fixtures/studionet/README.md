# Studionet certification fixture

`genreplay_fixture.py` is deliberately tiny certification infrastructure. It is not
distributed in the GenReplay Python wheel and is not product architecture.

Its single write method bounds user input to 32 characters, asks for a `YES` or `NO`
decision, rejects any other model output, sends that decision through strict equivalence,
and stores the observable result. It has no web dependency or mutable external source.

The source digest must be recorded with every deployment. Run the repository-local CLI
only, for example `node scripts/genlayer-local.mjs deploy --contract fixtures/studionet/genreplay_fixture.py --rpc https://studio.genlayer.com/api`.
