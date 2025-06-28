module bribery_voting::birber;

use std::string::{String};
use sui::table::{Table};
use bribery_voting::ballot::{Ballot};
use bribery_voting::flag;

/// Briber will give you the Flag
/// if you vote enough for Bad Candidate
/// and non for Good Candidate

const REQUIRED_CANDIDATE: address = @0xbad;
const REQUIRED_VOTES: u64 = 21;

public struct Briber has key {
    id: UID,
    given_list: Table<ID, bool>,
}

public fun get_flag(
    briber: &mut Briber,
    ballot: &Ballot,
    github_id: String,
    ctx: &TxContext,
) {
    let ballot_id = ballot.id();
    assert!(!briber.given_list.contains(ballot_id));
    let power_opt = ballot.voted().try_get(&required_candidate());
    assert!(power_opt.is_some());
    assert!(power_opt.destroy_some() >= required_votes());
    flag::emit_flag(ctx.sender(), ballot.id().to_bytes().to_string(), github_id);
}


public fun required_candidate(): address {
    REQUIRED_CANDIDATE
}


public fun required_votes(): u64 {
    REQUIRED_VOTES
}
