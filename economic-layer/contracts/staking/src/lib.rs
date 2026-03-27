use cosmwasm_std::{
    entry_point, to_json_binary, Addr, BankMsg, Binary, Coin, CosmosMsg, Deps, DepsMut, Env,
    MessageInfo, Response, StdError, StdResult,
};
use cw_storage_plus::{Item, Map};
use serde::{Deserialize, Serialize};

const OWNER: Item<Addr> = Item::new("owner");
const DENOM: Item<String> = Item::new("denom");
const STAKES: Map<&Addr, u128> = Map::new("stakes");

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct InstantiateMsg {
    pub owner: String,
    pub denom: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ExecuteMsg {
    Stake {},
    Unstake { amount: u128 },
    Slash { validator: String, amount: u128, reason: String },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    Stake { wallet: String },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct StakeResponse {
    pub wallet: String,
    pub amount: u128,
}

#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    _info: MessageInfo,
    msg: InstantiateMsg,
) -> StdResult<Response> {
    OWNER.save(deps.storage, &deps.api.addr_validate(&msg.owner)?)?;
    DENOM.save(deps.storage, &msg.denom)?;
    Ok(Response::new().add_attribute("action", "instantiate_staking"))
}

#[entry_point]
pub fn execute(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> StdResult<Response> {
    match msg {
        ExecuteMsg::Stake {} => stake(deps, info),
        ExecuteMsg::Unstake { amount } => unstake(deps, info, amount),
        ExecuteMsg::Slash {
            validator,
            amount,
            reason,
        } => slash(deps, info, validator, amount, reason),
    }
}

fn stake(deps: DepsMut, info: MessageInfo) -> StdResult<Response> {
    let denom = DENOM.load(deps.storage)?;
    let sent = info
        .funds
        .iter()
        .find(|c| c.denom == denom)
        .map(|c| c.amount.u128())
        .unwrap_or(0);

    if sent == 0 {
        return Err(StdError::generic_err("stake amount must be > 0"));
    }

    let current = STAKES.may_load(deps.storage, &info.sender)?.unwrap_or(0);
    STAKES.save(deps.storage, &info.sender, &(current + sent))?;

    Ok(Response::new()
        .add_attribute("action", "stake")
        .add_attribute("wallet", info.sender.to_string())
        .add_attribute("amount", sent.to_string()))
}

fn unstake(deps: DepsMut, info: MessageInfo, amount: u128) -> StdResult<Response> {
    if amount == 0 {
        return Err(StdError::generic_err("unstake amount must be > 0"));
    }

    let current = STAKES.may_load(deps.storage, &info.sender)?.unwrap_or(0);
    if current < amount {
        return Err(StdError::generic_err("insufficient staked balance"));
    }

    STAKES.save(deps.storage, &info.sender, &(current - amount))?;
    let denom = DENOM.load(deps.storage)?;

    let send = CosmosMsg::Bank(BankMsg::Send {
        to_address: info.sender.to_string(),
        amount: vec![Coin::new(amount, denom)],
    });

    Ok(Response::new()
        .add_message(send)
        .add_attribute("action", "unstake")
        .add_attribute("wallet", info.sender.to_string())
        .add_attribute("amount", amount.to_string()))
}

fn slash(
    deps: DepsMut,
    info: MessageInfo,
    validator: String,
    amount: u128,
    reason: String,
) -> StdResult<Response> {
    let owner = OWNER.load(deps.storage)?;
    if info.sender != owner {
        return Err(StdError::generic_err("only owner can slash validators"));
    }
    if amount == 0 {
        return Err(StdError::generic_err("slash amount must be > 0"));
    }

    let validator_addr = deps.api.addr_validate(&validator)?;
    let current = STAKES.may_load(deps.storage, &validator_addr)?.unwrap_or(0);
    if current < amount {
        return Err(StdError::generic_err("validator has insufficient stake"));
    }

    STAKES.save(deps.storage, &validator_addr, &(current - amount))?;

    Ok(Response::new()
        .add_attribute("action", "slash")
        .add_attribute("validator", validator_addr.to_string())
        .add_attribute("amount", amount.to_string())
        .add_attribute("reason", reason))
}

#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::Stake { wallet } => {
            let addr = deps.api.addr_validate(&wallet)?;
            let amount = STAKES.may_load(deps.storage, &addr)?.unwrap_or(0);
            to_json_binary(&StakeResponse {
                wallet: addr.to_string(),
                amount,
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cosmwasm_std::{
        coin, from_json, testing::mock_dependencies, testing::mock_env, testing::mock_info,
    };

    #[test]
    fn stake_flow() {
        let mut deps = mock_dependencies();

        instantiate(
            deps.as_mut(),
            mock_env(),
            mock_info("owner", &[]),
            InstantiateMsg {
                owner: "owner".to_string(),
                denom: "ugalaxy".to_string(),
            },
        )
        .unwrap();

        execute(
            deps.as_mut(),
            mock_env(),
            mock_info("validator1", &[coin(100, "ugalaxy")]),
            ExecuteMsg::Stake {},
        )
        .unwrap();

        let raw = query(
            deps.as_ref(),
            mock_env(),
            QueryMsg::Stake {
                wallet: "validator1".to_string(),
            },
        )
        .unwrap();
        let parsed: StakeResponse = from_json(raw).unwrap();
        assert_eq!(parsed.amount, 100);
    }
}
