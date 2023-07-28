from sources.subgraph.bins import GammaClient
from sources.subgraph.bins.enums import Chain, Protocol


class AccountData:
    def __init__(self, protocol: Protocol, chain: Chain, account_address: str):
        self.gamma_client = GammaClient(protocol, chain)
        self.gamma_client_mainnet = GammaClient(Protocol.UNISWAP, Chain.ETHEREUM)
        self.address = account_address.lower()
        self.decimal_factor = 10**18
        self.data: dict

    async def _get_data(self):
        query = """
        query accountHypervisor($accountAddress: String!) {
            account(
                id: $accountAddress
            ){
                parent { id }
                hypervisorShares {
                    hypervisor {
                        id
                        pool{
                            token0{ decimals }
                            token1{ decimals }
                        }
                        conversion {
                            baseTokenIndex
                            priceTokenInBase
                            priceBaseInUSD
                        }
                        totalSupply
                        tvl0
                        tvl1
                        tvlUSD
                    }
                    shares
                    initialToken0
                    initialToken1
                    initialUSD
                }
            }
        }
        """
        variables = {
            "accountAddress": self.address,
        }


        hypervisor_response = await self.gamma_client.query(query, variables)

        self.data = {
            "hypervisor": hypervisor_response["data"],
        }


class AccountInfo(AccountData):
    def _returns(self):
        returns = {}
        for share in self.data["hypervisor"]["account"]["hypervisorShares"]:
            if int(share["shares"]) <= 0:  # Workaround before fix in subgraph
                continue
            hypervisor_address = share["hypervisor"]["id"]
            initial_token0 = int(share["initialToken0"])
            initial_token1 = int(share["initialToken1"])
            initial_usd = float(share["initialUSD"])
            share_of_pool = int(share["shares"]) / int(
                share["hypervisor"]["totalSupply"]
            )
            tvl_usd = float(share["hypervisor"]["tvlUSD"])

            conversion = share["hypervisor"]["conversion"]

            base_token_index = int(conversion["baseTokenIndex"])
            price_token_in_base = float(conversion["priceTokenInBase"])
            price_base_in_usd = float(conversion["priceBaseInUSD"])

            if base_token_index == 0:
                token = initial_token1
                base = initial_token0
            elif base_token_index == 1:
                token = initial_token0
                base = initial_token1
            else:
                token = 0
                base = 0

            initial_token_current_usd = (
                token * price_token_in_base * price_base_in_usd
            ) + (base * price_base_in_usd)
            current_usd = share_of_pool * tvl_usd

            hypervisor_returns_percentage = (
                (current_usd / initial_token_current_usd) - 1
                if initial_token_current_usd > 0
                else 0
            )

            returns[hypervisor_address] = {
                "initialTokenUSD": initial_usd,
                "initialTokenCurrentUSD": initial_token_current_usd,
                "currentUSD": current_usd,
                "netMarketReturnsUSD": current_usd - initial_usd,
                "netMarketReturnsPercentage": f"{(current_usd /initial_usd) - 1:.2%}"
                if initial_usd > 0
                else "N/A",
                "hypervisorReturnsUSD": current_usd - initial_token_current_usd,
                "hypervisorReturnsPercentage": f"{hypervisor_returns_percentage:.2%}"
                if initial_token_current_usd > 0
                else "N/A",
            }

        return returns

    async def output(self, get_data=True):
        if get_data:
            await self._get_data()

        hypervisor_data = self.data["hypervisor"]

        has_hypervisor_data = bool(hypervisor_data.get("account"))


        if not has_hypervisor_data:
            return {}
            
        owner = hypervisor_data["account"]["parent"]["id"]

        account_info = {"owner": owner}

        if has_hypervisor_data:
            returns = self._returns()
            for hypervisor in hypervisor_data["account"]["hypervisorShares"]:
                if int(hypervisor["shares"]) <= 0:  # Workaround before fix in subgraph
                    continue
                hypervisor_id = hypervisor["hypervisor"]["id"]
                shares = int(hypervisor["shares"])
                total_supply = int(hypervisor["hypervisor"]["totalSupply"])
                share_of_supply = shares / total_supply if total_supply > 0 else 0
                tvl_usd = float(hypervisor["hypervisor"]["tvlUSD"])
                decimal0 = int(hypervisor["hypervisor"]["pool"]["token0"]["decimals"])
                decimal1 = int(hypervisor["hypervisor"]["pool"]["token1"]["decimals"])
                tvl0_decimal = float(hypervisor["hypervisor"]["tvl0"]) / 10**decimal0
                tvl1_decimal = float(hypervisor["hypervisor"]["tvl1"]) / 10**decimal1

                account_info[hypervisor_id] = {
                    "shares": shares,
                    "shareOfSupply": share_of_supply,
                    "balance0": tvl0_decimal * share_of_supply,
                    "balance1": tvl1_decimal * share_of_supply,
                    "balanceUSD": tvl_usd * share_of_supply,
                    "returns": returns[hypervisor_id],
                }

        return account_info
