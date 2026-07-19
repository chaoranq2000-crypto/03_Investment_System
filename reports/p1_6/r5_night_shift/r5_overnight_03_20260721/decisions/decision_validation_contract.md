# Night03 Decision Validation Contract

An approved decision is valid only when the physical Night02 queue, candidate
artifact, and review packet match their declared SHA-256 values; the occurrence
taxonomy matches the decision kind; reviewer identity and authority are external
and non-empty; and `reviewed_at` is timezone-aware and not in the future.

Validation does not resolve an occurrence. Resolution additionally requires an
independent passed execution or acceptance receipt with matching lineage and
decision digest.
