import numpy as np

def fourth_down_decision(our_score, opp_score, time_remaining_min, distance_to_first_down, field_position,
                         avg_net_punt_yards=40, kickoff_start_pos=27):
    """
    Determines the best 4th down decision: 'Punt', 'GO', or 'Kick'.
    Returns a tuple: (decision, additional_info)
    - additional_info: For 'Punt', needed net punt distance (float); for 'Kick', needed FG % (float); None for 'GO'.
    """
    if field_position < 1 or field_position > 99:
        raise ValueError("Field position must be between 1 and 99.")
    
    point_diff = our_score - opp_score
    fg_dist = 100 - field_position + 17
    
    # EP polynomial coefficients
    a, b, c, d = 1.03395910e-05, -9.54314154e-04, 5.65134209e-02, -3.51784512e-01
    
    def ep(pos):
        pos = max(1, min(99, pos))
        return a * pos**3 + b * pos**2 + c * pos + d
    
    # Conversion probability
    def get_p_conv(ytg):
        conv_rates = {1: 0.69, 2: 0.60, 3: 0.53, 4: 0.48, 5: 0.44, 6: 0.40, 7: 0.36, 8: 0.33, 9: 0.31, 10: 0.29}
        return conv_rates.get(min(ytg, 10), 0.25)
    
    # FG make probability (estimated for distance)
    def get_p_make(dist):
        if dist < 30: return 0.95
        elif dist < 40: return 0.90
        elif dist < 50: return 0.80
        elif dist < 60: return 0.65
        else: return 0.40
    
    p_conv = get_p_conv(distance_to_first_down)
    p_make_est = get_p_make(fg_dist)  # Estimated for output if needed, but not used in thresholds
    
    # EP for GO
    new_pos = min(99, field_position + distance_to_first_down)
    ep_go = p_conv * ep(new_pos) + (1 - p_conv) * (-ep(100 - field_position))
    
    # EP for Punt (using avg_net_punt_yards)
    if field_position + avg_net_punt_yards > 100:
        opp_fp_punt = 20
    else:
        opp_fp_punt = 100 - field_position - avg_net_punt_yards
    ep_punt = -ep(opp_fp_punt)
    
    # EP for KICK
    opp_fp_miss = max(20, 107 - field_position)
    ep_kickoff = ep(kickoff_start_pos)
    ep_miss = ep(opp_fp_miss)
    ep_kick = p_make_est * (3 - ep_kickoff) + (1 - p_make_est) * (-ep_miss)
    
    # Late-game heuristics
    if time_remaining_min < 2:
        if point_diff > 0:  # Leading
            if fg_dist <= 50:
                decision = 'Kick'
            else:
                decision = 'Punt'
        elif point_diff < 0:  # Trailing
            trailing_by = -point_diff
            if trailing_by <= 3 and fg_dist <= 55:
                decision = 'Kick'
            elif trailing_by <= 8:
                decision = 'GO'
            else:
                decision = 'Punt'
        else:  # Tied, use EP
            eps = {'Punt': ep_punt, 'GO': ep_go, 'Kick': ep_kick}
            decision = max(eps, key=eps.get)
    else:
        # Normal case: max EP
        eps = {'Punt': ep_punt, 'GO': ep_go, 'Kick': ep_kick}
        decision = max(eps, key=eps.get)
    
    # Calculate additional info (thresholds)
    if decision == 'GO':
        return decision, None
    
    elif decision == 'Punt':
        max_other = max(ep_go, ep_kick)
        # Solve for fp where -ep(fp) == max_other => ep(fp) == -max_other
        roots = np.roots([a, b, c, d + (-max_other)])  # Solve a x^3 + b x^2 + c x + (d - (-max_other)) = 0
        valid_roots = [r.real for r in roots if r.imag == 0 and 1 <= r.real <= 99]
        if not valid_roots:
            needed_net = float('inf')  # Impossible
        else:
            fp_threshold = max(valid_roots)  # Largest fp where still better (since higher fp worse for us)
            needed_net = max(0, 100 - field_position - fp_threshold)
            if needed_net > 100 - field_position:
                # Check if touchback suffices
                if -ep(20) >= max_other:
                    needed_net = 100 - field_position + 1  # Minimum to cause touchback
                else:
                    needed_net = float('inf')
        return decision, round(needed_net, 1)
    
    elif decision == 'Kick':
        max_other = max(ep_go, ep_punt)
        a_term = 3 - ep_kickoff + ep_miss
        b_term = -ep_miss
        if a_term <= 0:
            needed_pct = 0.0  # Always better or impossible
        else:
            needed_p_make = max(0, min(1, (max_other - b_term) / a_term))
        return decision, round(needed_p_make * 100, 1)