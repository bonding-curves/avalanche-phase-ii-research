"""The bottom layer: errors, hashing, units, the clock, dataset contracts and receipts, run paths.

Everything else may import it, and it imports nothing else in the package. Modules arrive here at restructure step
`M1`. Until then the package holds only the alias helper that keeps old import paths working during the moves.
"""
