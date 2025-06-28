#[allow(unused_variable, lint(custom_state_change))]
module game::challenge {
    use sui::event;

    const EINVALID_KILLS: u64 = 0;
    const EINVALID_LEVEL: u64 = 1;
    const EINVALID_ADMIN: u64 = 2;

    public struct PackageSender has key {
        id: UID,
        sender: address
    }

    public struct Player has key, store {
        id: UID,
        owner: address,
        level: u64,
        kills: u64,
    }

    public struct AdminCap has key, store {
        id: UID,
    }

    public struct FlagEvent has copy, drop {
        owner: address,
        flag: bool,
    }


    fun init(ctx: &mut TxContext) {
        let packageSender = PackageSender {
            id: object::new(ctx),
            sender: ctx.sender(),
        };

        transfer::transfer(packageSender, ctx.sender())
    }

    public fun mint_cap(ctx: &mut TxContext): AdminCap {
        AdminCap {
            id: object::new(ctx),
        }
    }

    public entry fun transfer_cap(sender: &PackageSender, admin: address, ctx: &mut TxContext) {
        assert!( ctx.sender() == sender.sender, EINVALID_ADMIN);
        let adminCap = mint_cap(ctx);
        transfer::transfer(adminCap, admin);
    }

    public entry fun create_player(ctx: &mut TxContext) {
        let player = Player {
            id: object::new(ctx),
            owner: ctx.sender(),
            level: 0,
            kills: 0,
        };

        transfer::transfer(player, ctx.sender());
    }

    public entry fun attack(player: &mut Player, ctx: &mut TxContext) {
        player.kills = player.kills + 1;
    }

    public entry fun level_up(player: &mut Player, ctx: &mut TxContext) {
        assert!(player.kills >= 10, EINVALID_KILLS);
        player.level = player.level + 1;
        player.kills = player.kills - 10;
    }

    public entry fun check(player: Player, admin: address, ctx: &mut TxContext) {
        if (player.level >= 10 ) {
            transfer::transfer(player, admin);
        } else {
            abort EINVALID_LEVEL
        }
    }

    public entry fun receive_rewards(_: &AdminCap, player: Player, ctx: &mut TxContext) {
        let owner = player.owner;

        event::emit(FlagEvent {
            owner: owner,
            flag: true,
        });

        transfer::transfer(player, owner)

    }
}


