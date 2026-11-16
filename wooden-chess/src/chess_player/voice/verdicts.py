"""Chess verdicts decided by python-chess + Stockfish, never by the language model. The model only phrases them.

classify(swing_cp): how much a move changed the evaluation for the side that played it (centipawns, negative = it lost that much).
"""
BLUNDER, MISTAKE, INACCURACY, GOOD, GREAT = "blunder", "mistake", "inaccuracy", "good move", "great move"
LIMITS = ((-300, BLUNDER), (-150, MISTAKE), (-60, INACCURACY))  # eval lost by the mover (cp)
GREAT_GAIN_CP = 100


def classify(mover_swing_cp: int) -> str:
    """mover_swing_cp = eval change from the mover's point of view (+ = the move helped the mover)."""
    for limit, name in LIMITS:
        if mover_swing_cp <= limit:
            return name
    return GREAT if mover_swing_cp >= GREAT_GAIN_CP else GOOD


def human_move_facts(san, mover_swing_cp, better_san=None, eval_text="", check=False):
    """One factual sentence for the model, e.g. 'The human played Qh5: a blunder (lost about 3.4 pawns). Stockfish prefers Nf3. Evaluation now +2.1 (White's view).'"""
    v = classify(mover_swing_cp)
    s = f"The human played {san}: {'a ' if v != GOOD else 'a '}{v}"
    if mover_swing_cp <= LIMITS[-1][0]:
        s += f" (lost about {abs(mover_swing_cp) / 100:.1f} pawns)"
    elif mover_swing_cp >= GREAT_GAIN_CP:
        s += f" (gained about {mover_swing_cp / 100:.1f} pawns)"
    s += "."
    if better_san and v in (BLUNDER, MISTAKE, INACCURACY):
        s += f" Stockfish preferred {better_san}."
    if check:
        s += " It gives check."
    if eval_text:
        s += f" Evaluation now {eval_text} (White's view)."
    return s


def illegal_facts(move_text, why):
    return f"The human tried {move_text}, which is ILLEGAL (a foul): {why}. The move was NOT accepted; they must take it back and play a legal move."
