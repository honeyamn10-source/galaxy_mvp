use cosmwasm_std::{
    entry_point, to_json_binary, Addr, BankMsg, Binary, Coin, CosmosMsg, Deps, DepsMut, Env,
    MessageInfo, Response, StdError, StdResult,
};
use cw_storage_plus::{Item, Map};
use serde::{Deserialize, Serialize};

const OWNER: Item<Addr> = Item::new("owner");
const REWARD_AMOUNT: Item<u128> = Item::new("reward_amount");
const REWARD_DENOM: Item<String> = Item::new("reward_denom");
const PAID_TX: Map<&str, bool> = Map::new("paid_tx");

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct InstantiateMsg {
    pub owner: String,
    pub reward_amount: u128,
    pub reward_denom: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ExecuteMsg {
    RewardVerifiedEvent {
        tx_hash: String,
        device_id: String,
        wallet: String,
        confidence: f64,
    },
    UpdateConfig {
        reward_amount: u128,
        reward_denom: String,
    },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    Config {},
    RewardStatus { tx_hash: String },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct ConfigResponse {
    pub owner: String,
    pub reward_amount: u128,
    pub reward_denom: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct RewardStatusResponse {
    pub tx_hash: String,
    pub paid: bool,
}

#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    _info: MessageInfo,
    msg: InstantiateMsg,
) -> StdResult<Response> {
    OWNER.save(deps.storage, &deps.api.addr_validate(&msg.owner)?)?;
    REWARD_AMOUNT.save(deps.storage, &msg.reward_amount)?;
    REWARD_DENOM.save(deps.storage, &msg.reward_denom)?;

    Ok(Response::new().add_attribute("action", "instantiate_reward"))
}

#[entry_point]
pub fn execute(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> StdResult<Response> {
    match msg {
        ExecuteMsg::RewardVerifiedEvent {
            tx_hash,
            device_id,
            wallet,
            confidence,
        } => reward_verified_event(deps, info, tx_hash, device_id, wallet, confidence),
        ExecuteMsg::UpdateConfig {
            reward_amount,
            reward_denom,
        } => update_config(deps, info, reward_amount, reward_denom),
    }
}

fn assert_owner(deps: DepsMut, sender: &Addr) -> StdResult<()> {
    let owner = OWNER.load(deps.storage)?;
    if owner != *sender {
        return Err(StdError::generic_err("only owner can execute this action"));
    }
    Ok(())
}

fn reward_verified_event(
    deps: DepsMut,
    info: MessageInfo,
    tx_hash: String,
    device_id: String,
    wallet: String,
    confidence: f64,
) -> StdResult<Response> {
    assert_owner(deps.branch(), &info.sender)?;

    if tx_hash.trim().is_empty() {
        return Err(StdError::generic_err("tx_hash is required"));
    }
    if confidence < 0.8 {
        return Err(StdError::generic_err("event not eligible for reward"));
    }
    if PAID_TX.may_load(deps.storage, tx_hash.as_str())?.unwrap_or(false) {
        return Err(StdError::generic_err("reward already issued for tx"));
    }

    let recipient = deps.api.addr_validate(wallet.trim())?;
    let amount = REWARD_AMOUNT.load(deps.storage)?;
    let denom = REWARD_DENOM.load(deps.storage)?;

    PAID_TX.save(deps.storage, tx_hash.as_str(), &true)?;

    let reward_msg = CosmosMsg::Bank(BankMsg::Send {
        to_address: recipient.to_string(),
        amount: vec![Coin::new(amount, denom.clone())],
    });

    Ok(Response::new()
        .add_message(reward_msg)
        .add_attribute("action", "reward_verified_event")
        .add_attribute("device_id", device_id)
        .add_attribute("tx_hash", tx_hash)
        .add_attribute("recipient", recipient.to_string())
        .add_attribute("amount", amount.to_string())
        .add_attribute("denom", denom))
}

fn update_config(
    deps: DepsMut,
    info: MessageInfo,
    reward_amount: u128,
    reward_denom: String,
) -> StdResult<Response> {
    assert_owner(deps.branch(), &info.sender)?;
    REWARD_AMOUNT.save(deps.storage, &reward_amount)?;
    REWARD_DENOM.save(deps.storage, &reward_denom)?;

    Ok(Response::new()
        .add_attribute("action", "update_config")
        .add_attribute("reward_amount", reward_amount.to_string())
        .add_attribute("reward_denom", reward_denom))
}

#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::Config {} => {
            let owner = OWNER.load(deps.storage)?;
            let reward_amount = REWARD_AMOUNT.load(deps.storage)?;
            let reward_denom = REWARD_DENOM.load(deps.storage)?;
            to_json_binary(&ConfigResponse {
                owner: owner.to_string(),
                reward_amount,
                reward_denom,
            })
        }
        QueryMsg::RewardStatus { tx_hash } => {
            let paid = PAID_TX.may_load(deps.storage, tx_hash.as_str())?.unwrap_or(false);
            to_json_binary(&RewardStatusResponse { tx_hash, paid })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cosmwasm_std::{from_json, testing::mock_dependencies, testing::mock_env, testing::mock_info};

    #[test]
    fn tracks_reward_status() {
        let mut deps = mock_dependencies();

        instantiate(
            deps.as_mut(),
            mock_env(),
            mock_info("owner", &[]),
            InstantiateMsg {
                owner: "owner".to_string(),
                reward_amount: 100,
                reward_denom: "ugalaxy".to_string(),
            },
        )
        .unwrap();

        execute(
            deps.as_mut(),
            mock_env(),
            mock_info("owner", &[]),
            ExecuteMsg::RewardVerifiedEvent {
                tx_hash: "TX001".to_string(),
                device_id: "planet-1".to_string(),
                wallet: "planet_wallet".to_string(),
                confidence: 0.95,
            },
        )
        .unwrap();

        let raw = query(
            deps.as_ref(),
            mock_env(),
            QueryMsg::RewardStatus {
                tx_hash: "TX001".to_string(),
            },
        )
        .unwrap();
        let parsed: RewardStatusResponse = from_json(raw).unwrap();
        assert!(parsed.paid);
    }
}
