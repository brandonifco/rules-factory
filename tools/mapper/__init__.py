"""The mapper: what turns a corpus into a candidate map, and the record of how.

One of the three subsystems the map contract joins (0032). It takes a pinned corpus, its
manifest, an adapter and a mapping protocol, and produces a map and the evidence that the
mapping was done the way the protocol says this corpus has to be read. It imports
`mapcontract` and nothing else in the repository: it knows nothing of the validation that
certifies its product, and nothing of the factory that builds an engine from it.

What lives here, and what does not. The mapping *method* -- what a mapper does, and why -- is
[docs/method.md](../../docs/method.md), and it stays a document, because most of it is judgement
a program cannot make. What lives here is the part of it that is mechanical: the protocol that
says how a particular corpus communicates rules, and the interrogation that a protocol obliges.

The distinction that matters is producer and verifier. This subsystem says *this is my reading
of the corpus, and here is what I did to reach it*. `tools/mapvalidator/` says *prove you satisfied
the contract*. They are apart for the reason production code is not its own only test oracle,
and absorbing one into the other would make a map its own only judge.
"""
