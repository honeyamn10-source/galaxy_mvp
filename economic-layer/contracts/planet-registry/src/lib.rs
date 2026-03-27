use cosmwasm_std::{
    entry_point, to_json_binary, Addr, Binary, Deps, DepsMut, Env, MessageInfo, Response, StdError,
    StdResult,
};
use cw_storage_plus::{Item, Map};
use serde::{Deserialize, Serialize};

const OWNER: Item<Addr> = Item::new("owner");
const PLANETS: Map<&str, Addr> = Map::new("planets");

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct InstantiateMsg {
    pub owner: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ExecuteMsg {
    RegisterPlanet { device_id: String, wallet: String },
    RemovePlanet { device_id: String },
    TransferOwnership { owner: String },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    Planet { device_id: String },
    Owner {},
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct PlanetResponse {
    pub device_id: String,
    pub wallet: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct OwnerResponse {
    pub owner: String,
}

#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    _info: MessageInfo,
    msg: InstantiateMsg,
) -> StdResult<Response> {
    let owner = deps.api.addr_validate(&msg.owner)?;
    OWNER.save(deps.storage, &owner)?;

    Ok(Response::new().add_attribute("action", "instantiate_registry"))
}

#[entry_point]
pub fn execute(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> StdResult<Response> {
    match msg {
        ExecuteMsg::RegisterPlanet { device_id, wallet } => register_planet(deps, info, device_id, wallet),
        ExecuteMsg::RemovePlanet { device_id } => remove_planet(deps, info, device_id),
        ExecuteMsg::TransferOwnership { owner } => transfer_ownership(deps, info, owner),
    }
}

fn assert_owner(deps: DepsMut, sender: &Addr) -> StdResult<()> {
    let owner = OWNER.load(deps.storage)?;
    if owner != *sender {
        return Err(StdError::generic_err("only owner can mutate registry"));
    }
    Ok(())
}

fn register_planet(
    deps: DepsMut,
    info: MessageInfo,
    device_id: String,
    wallet: String,
) -> StdResult<Response> {
    assert_owner(deps.branch(), &info.sender)?;
    if device_id.trim().is_empty() {
        return Err(StdError::generic_err("device_id is required"));
    }

    let wallet_addr = deps.api.addr_validate(wallet.trim())?;
    PLANETS.save(deps.storage, device_id.as_str(), &wallet_addr)?;

    Ok(Response::new()
        .add_attribute("action", "register_planet")
        .add_attribute("device_id", device_id)
        .add_attribute("wallet", wallet_addr.to_string()))
}

fn remove_planet(deps: DepsMut, info: MessageInfo, device_id: String) -> StdResult<Response> {
    assert_owner(deps.branch(), &info.sender)?;
    PLANETS.remove(deps.storage, device_id.as_str());

    Ok(Response::new()
        .add_attribute("action", "remove_planet")
        .add_attribute("device_id", device_id))
}

fn transfer_ownership(deps: DepsMut, info: MessageInfo, owner: String) -> StdResult<Response> {
    assert_owner(deps.branch(), &info.sender)?;
    let next_owner = deps.api.addr_validate(owner.trim())?;
    OWNER.save(deps.storage, &next_owner)?;

    Ok(Response::new()
        .add_attribute("action", "transfer_ownership")
        .add_attribute("owner", next_owner.to_string()))
}

#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::Planet { device_id } => {
            let wallet = PLANETS
                .may_load(deps.storage, device_id.as_str())?
                .ok_or_else(|| StdError::not_found("planet"))?;
            to_json_binary(&PlanetResponse {
                device_id,
                wallet: wallet.to_string(),
            })
        }
        QueryMsg::Owner {} => {
            let owner = OWNER.load(deps.storage)?;
            to_json_binary(&OwnerResponse {
                owner: owner.to_string(),
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cosmwasm_std::{from_json, testing::mock_dependencies, testing::mock_env, testing::mock_info};

    #[test]
    fn register_and_query_planet() {
        let mut deps = mock_dependencies();

        instantiate(
            deps.as_mut(),
            mock_env(),
            mock_info("owner", &[]),
            InstantiateMsg {
                owner: "owner".to_string(),
            },
        )
        .unwrap();

        execute(
            deps.as_mut(),
            mock_env(),
            mock_info("owner", &[]),
            ExecuteMsg::RegisterPlanet {
                device_id: "planet-1".to_string(),
                wallet: "wallet1".to_string(),
            },
        )
        .unwrap();

        let raw = query(
            deps.as_ref(),
            mock_env(),
            QueryMsg::Planet {
                device_id: "planet-1".to_string(),
            },
        )
        .unwrap();

        let parsed: PlanetResponse = from_json(raw).unwrap();
        assert_eq!(parsed.wallet, "wallet1");
    }
}
