from substrateinterface import SubstrateInterface
from prometheus_client import start_http_server, Gauge
import asyncio
import time
import signal
import sys
import logging
from typing import Dict, List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

VALIDATOR_SELF_STAKE = Gauge(
    "ternoa_validator_self_stake",
    "Validator self stake in CAPS",
    ["validator", "name", "status"],
)

VALIDATOR_CAPS_IN = Gauge(
    "ternoa_validator_caps_in",
    "CAPS transferred into validator",
    ["validator", "name", "type"],
)

VALIDATOR_CAPS_OUT = Gauge(
    "ternoa_validator_caps_out",
    "CAPS transferred out of validator",
    ["validator", "name", "type"],
)

VALIDATOR_REWARDS = Gauge(
    "ternoa_validator_rewards",
    "Validator rewards in CAPS",
    ["validator", "name", "era"],
)

VALIDATOR_NOMINATIONS = Gauge(
    "ternoa_validator_nominations",
    "Validator nominations in CAPS",
    ["validator", "name", "status"],
)

VALIDATOR_TOTAL_STAKE = Gauge(
    "ternoa_validator_total_stake",
    "Validator total stake in CAPS",
    ["validator", "name", "status"],
)

VALIDATOR_NOMINATOR_COUNT = Gauge(
    "ternoa_validator_nominator_count",
    "Number of nominators for validator",
    ["validator", "name", "status"],
)

SUBSTRATE_URL = "wss://mainnet.ternoa.network"
MAX_RETRIES = 5
RETRY_DELAY = 5
previous_stakes = {}

async def create_connection():
    for attempt in range(MAX_RETRIES):
        try:
            substrate = SubstrateInterface(
                url=SUBSTRATE_URL,
                ss58_format=42,
                type_registry_preset="substrate-node-template",
                auto_discover=True,
                use_remote_preset=True,
                ws_options={
                    'max_size': None,
                    'max_queue': None,
                    'ping_interval': 20,
                    'ping_timeout': 20
                }
            )
            substrate.query("System", "Number")
            return substrate
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to connect after {MAX_RETRIES} attempts: {e}")
                raise
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(RETRY_DELAY)

def extract_identity_value(value):
    if not value:
        return ""
    try:
        if isinstance(value, dict):
            if 'Raw' in value:
                return str(value['Raw'])
            if 'None' in value:
                return ""
            return str(value)
        elif hasattr(value, 'decode'):
            return value.decode()
        return str(value)
    except Exception:
        return str(value)

async def get_era_rewards(substrate, validator: str, era_index: int) -> float:
    try:
        reward_points = substrate.query(
            "Staking",
            "ErasRewardPoints",
            [era_index]
        )
        if reward_points and hasattr(reward_points, 'value'):
            try:
                if isinstance(reward_points.value, list):
                    total_points = 0
                    validator_points = 0
                    
                    # First pass - calculate total points
                    for entry in reward_points.value:
                        if isinstance(entry, list) and len(entry) >= 2:
                            total_points += float(entry[1])
                    
                    # Second pass - find validator points
                    for entry in reward_points.value:
                        if isinstance(entry, list) and len(entry) >= 2:
                            if str(entry[0]) == validator:
                                validator_points = float(entry[1])
                                break
                    
                    if total_points == 0:
                        total_points = 1  # Avoid division by zero
                    
                    era_reward = substrate.query(
                        "Staking",
                        "ErasValidatorReward",
                        [era_index]
                    )
                    if era_reward and era_reward.value:
                        total_reward = float(era_reward.value) / 1e18
                        validator_reward = (validator_points / total_points) * total_reward
                        return validator_reward
            except Exception as e:
                logger.error(f"Error processing reward points for validator {validator}: {e}")
    except Exception as e:
        logger.error(f"Error getting era rewards for validator {validator}: {e}")
    return 0.0

async def get_era_slashes(substrate, validator: str, era_index: int) -> float:
    try:
        return 0.0
    except Exception as e:
        logger.error(f"Error getting era slashes for validator {validator}: {e}")
    return 0.0

async def track_stake_movements(
    validator: str,
    name: str,
    current_stake: float,
    previous_stake: Optional[float]
) -> Tuple[float, float]:
    if previous_stake is None:
        return 0.0, 0.0

    stake_difference = current_stake - previous_stake
    
    if stake_difference > 0:
        VALIDATOR_CAPS_IN.labels(
            validator=validator,
            name=name,
            type="nomination"
        ).set(stake_difference)
        return stake_difference, 0.0
    elif stake_difference < 0:
        abs_difference = abs(stake_difference)
        VALIDATOR_CAPS_OUT.labels(
            validator=validator,
            name=name,
            type="unstake"
        ).set(abs_difference)
        return 0.0, abs_difference
    
    return 0.0, 0.0

async def get_validator_stakes(substrate, validators: List[str]) -> Dict[str, dict]:
    stakes = {}
    try:
        active_era = substrate.query("Staking", "ActiveEra")
        era_index = active_era.value["index"]

        for validator in validators:
            try:
                exposure = substrate.query("Staking", "ErasStakers", [era_index, validator])
                if exposure:
                    own = float(exposure.value["own"]) / 1e18
                    total = float(exposure.value["total"]) / 1e18
                    others = total - own
                    nominators = len(exposure.value.get("others", []))
                    
                    rewards = await get_era_rewards(substrate, validator, era_index)
                    slashes = await get_era_slashes(substrate, validator, era_index)
                    
                    stakes[validator] = {
                        "self_stake": own,
                        "total_stake": total,
                        "nominations": others,
                        "nominator_count": nominators,
                        "rewards": rewards,
                        "slashes": slashes,
                    }
            except Exception as e:
                logger.error(f"Error getting stake for validator {validator}: {e}")
                stakes[validator] = {
                    "self_stake": 0,
                    "total_stake": 0,
                    "nominations": 0,
                    "nominator_count": 0,
                    "rewards": 0,
                    "slashes": 0,
                }
    except Exception as e:
        logger.error(f"Error fetching active era: {e}")
        raise

    return stakes

async def get_identities(substrate, wallets: List[str]) -> Dict[str, dict]:
    identities = {}

    for wallet in wallets:
        try:
            identity_info = {
                "display": "",
                "legal": "",
                "web": "",
                "riot": "",
                "email": "",
                "twitter": "",
            }

            parent = substrate.query("Identity", "SuperOf", [wallet])

            if parent and parent.value:
                try:
                    sub_identity_raw = parent.value[1]
                    sub_identity_name = extract_identity_value(sub_identity_raw)
                    parent_wallet = str(parent.value[0])
                    
                    identity_raw = substrate.query(
                        "Identity", "IdentityOf", [parent_wallet]
                    )

                    if identity_raw and identity_raw.value:
                        info = identity_raw.value.get("info", {})
                        display_name = extract_identity_value(info.get("display", ""))
                        identity_info = {
                            "display": (
                                f"{display_name}/{sub_identity_name}"
                                if display_name
                                else sub_identity_name
                            ),
                            "legal": extract_identity_value(info.get("legal", "")),
                            "web": extract_identity_value(info.get("web", "")),
                            "riot": extract_identity_value(info.get("riot", "")),
                            "email": extract_identity_value(info.get("email", "")),
                            "twitter": extract_identity_value(info.get("twitter", "")),
                        }
                except Exception as e:
                    logger.error(f"Error processing parent identity for {wallet}: {e}")
            else:
                try:
                    identity_raw = substrate.query("Identity", "IdentityOf", [wallet])
                    if identity_raw and identity_raw.value:
                        info = identity_raw.value.get("info", {})
                        identity_info = {
                            "display": extract_identity_value(info.get("display", "")),
                            "legal": extract_identity_value(info.get("legal", "")),
                            "web": extract_identity_value(info.get("web", "")),
                            "riot": extract_identity_value(info.get("riot", "")),
                            "email": extract_identity_value(info.get("email", "")),
                            "twitter": extract_identity_value(info.get("twitter", "")),
                        }
                except Exception as e:
                    logger.error(f"Error processing identity for {wallet}: {e}")

            identities[wallet] = identity_info

        except Exception as e:
            logger.error(f"Error processing identity for wallet {wallet}: {e}")
            identities[wallet] = {
                "display": "",
                "legal": "",
                "web": "",
                "riot": "",
                "email": "",
                "twitter": "",
            }

    return identities

async def update_metrics(substrate):
    global previous_stakes
    
    try:
        validators_result = substrate.query_map("Staking", "Validators")
        validators = [str(v[0]) for v in validators_result]

        active_validators = substrate.query("Session", "Validators")
        active_validators = [str(v) for v in active_validators]

        validator_stakes = await get_validator_stakes(substrate, validators)
        validators_id = await get_identities(substrate, validators)

        active_era = substrate.query("Staking", "ActiveEra")
        current_era = active_era.value["index"]

        for validator, stake_info in validator_stakes.items():
            status = "active" if validator in active_validators else "waiting"
            name = validators_id.get(validator, {}).get("display", "") or validator[:20]

            current_total = stake_info["total_stake"]
            previous_total = previous_stakes.get(validator, {}).get("total_stake")
            
            await track_stake_movements(
                validator,
                name,
                current_total,
                previous_total
            )

            VALIDATOR_SELF_STAKE.labels(
                validator=validator,
                name=name,
                status=status
            ).set(stake_info["self_stake"])
            
            VALIDATOR_NOMINATIONS.labels(
                validator=validator,
                name=name,
                status=status
            ).set(stake_info["nominations"])
            
            VALIDATOR_TOTAL_STAKE.labels(
                validator=validator,
                name=name,
                status=status
            ).set(stake_info["total_stake"])
            
            VALIDATOR_NOMINATOR_COUNT.labels(
                validator=validator,
                name=name,
                status=status
            ).set(stake_info["nominator_count"])

            if stake_info["rewards"] > 0:
                VALIDATOR_REWARDS.labels(
                    validator=validator,
                    name=name,
                    era=str(current_era)
                ).set(stake_info["rewards"])

        previous_stakes = validator_stakes

    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
        raise

async def metrics_loop():
    while True:
        substrate = None
        try:
            substrate = await create_connection()
            logger.info("Connected to Ternoa network")

            while True:
                logger.info("Updating metrics...")
                start_time = time.time()
                await update_metrics(substrate)
                elapsed_time = time.time() - start_time
                logger.info(f"Updated metrics in {elapsed_time:.2f} seconds")
                await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Error in metrics loop: {e}")
            await asyncio.sleep(5)
        finally:
            if substrate:
                try:
                    substrate.close()
                except:
                    pass

def signal_handler(sig, frame):
    logger.info("Shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    start_http_server(8000)
    logger.info("Prometheus metrics server started on port 8000")

    try:
        asyncio.run(metrics_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)