
module bribery_voting::candidates;

use bribery_voting::ballot::{VoteRequest};

public struct Candidate has key {
    id: UID,
	account: address,
	total_votes: u64,
}

public fun register(
    ctx: &mut TxContext,
) {
    let candidate = Candidate {
        id: object::new(ctx),
        account: ctx.sender(),
        total_votes: 0,
    };
    transfer::share_object(candidate);
}

public fun amend_account(
    candiate: &mut Candidate,
    account: address,
) {
    candiate.account = account;
}

public fun vote(
    candiate: &mut Candidate,
    request: &mut VoteRequest,
    amount: u64,
) {
    let gain_votes = request.deduct_voting_power(amount);
    candiate.total_votes = candiate.total_votes + gain_votes;
}
