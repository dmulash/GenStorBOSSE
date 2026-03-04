# surplusbosse/model.py
import copy

DEFAULTS = {
    "BatteryCapacity": 60,  # MW_cap
    "BatteryDuration": 4,   # hours
    "ESS_ILR": 1,
    "ESSWeight": 9.4,  # kg/kWh_cap
    "ESSLabor": 0.22,  # hours/kWh_cap
    "ESSElectricity": 30.5, # cap
    "ESSDepreciation": 0.11, # %/100
    "ESSProfit": 0.25,  # %/100
    "Tariff201": 0.1425,  # %/100
    "Tariff301": 0.25,  # %/100
    "GeneralDuty": 0.034,  # %/100
    "Battery45X": 10,  # %/100
    "45XPassthrough": 0.5,  # %/100
    # BESS Manufacturing
    "LiIonCells": 75.0,  # $/kWh-cap
    "BatteryPacks": 25.0,  # $/kWh-cap
    "Enclosure": 20.0,  # $/kWh-cap
    "BidirectionalInverter": 100.0,  # $/kWac
    "LaborCost": 2_500_000,  # $
    "LaborRate": 34.0,  # $/hour
    "ElectricityCost": 0.08,  # $/kWh
    "DepreciationCost": 7.0,  #$/kWh-cap/yr
    "MaintenanceCost": 0.28,  #
    "ProfitCost": 0.0,
    "ShippingCost": 1.0,  # $/kg
    "PassthroughCost": 0.0, # $/kWh-cap
    # SBOS
    "SitePrepStaging": 50.0,
    "ConcretePads": 0.10,
    # EBOS
    "Transformer": 40.0,
    "SwitchGear": 6.5,
    "Conductors": 21.0,
    "BreakerDC": 15.0,
    "Grounding": 9.5,
    "SCADA": 3.5,
    "Substation": 33.0,
    "TransmissionCost": 680_000,
    "Transmission": 17.0,
    "NetworkUpgrade": 0.0,
    "EBOSShipping": 1.2,
    # Installation
    "ESSInstallLabor": 2.15,
    "ESSInstallHourlyLabor": 27.5,
    "LaborBurdenRate": 0.54,
    "SalesTaxRate": 0.058,
    "ContingencyRate": 0.025,
    "OverheadRate": 0.01,
    "DeveloperProfit": 0.05,
    "AnnualESSProduction": 1_000_000,
    "AnnualEPCInstallation": 600_000,
    "ESSContainer": 3,
    "ESSInstallationArea": 80,
    "EBOSWeight": 2,
    "ConcretePadThickness": 0.5,
    "ConcreteDensity": 2400,
    # Soft Costs
    "Warehousing": 0.55,
    "Logistics": 0.1,
    "Engineering": 3.0,
    "EngineeringFixed": 50_000,
    "Permits": 200_000,
    "Interconnect": 35.0,
    "InterconnectFixed": 85_000,
    "Outreach": 1.0,
    "SalesTaxCost": 14.61,
    "ContingencyCost": 6.3,
    "ManagementCost": 2.52,
    "ManagementFixed": 1_000_000,
    "ProfitCostSoft": 12.59
}


class GenStorBOSSEModel:
    def __init__(self, user_config: dict = None):
        # Load defaults and override with user input
        self.config = copy.deepcopy(DEFAULTS)
        if user_config:
            self.config.update(user_config)

    def run(self):
        total_bess = (
            self.config["LiIonCells"] * self.config["AnnualESSProduction"]
            + self.config["BatteryPacks"] * self.config["AnnualESSProduction"]
            + self.config["Enclosure"] * self.config["AnnualESSProduction"]
        )
        total_sbos = self.config["SitePrepStaging"] * self.config["ESSInstallationArea"]
        total_ebos = self.config["Transformer"] * self.config["AnnualEPCInstallation"]
        total_cost = total_bess + total_sbos + total_ebos

        return {
            "total_bess": total_bess,
            "total_sbos": total_sbos,
            "total_ebos": total_ebos,
            "total_cost": total_cost,
        }

    def get_li_ion_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config

        # 1. Cells + Tariffs
        li_ion_cells = cfg["LiIonCells"] * (1 + cfg["GeneralDuty"] + cfg["Tariff301"])
        
        # 2. Logistics & Setup
        battery_duration = cfg["BatteryDuration"]
        ilr = cfg["ESS_ILR"]
        
        # 3. Component sums
        labor = (cfg["LaborCost"] / cfg["AnnualESSProduction"]) + (cfg["LaborRate"] * cfg["ESSLabor"])
        electricity = cfg["ElectricityCost"] * cfg["ESSElectricity"]
        depreciation = cfg["DepreciationCost"] * cfg["ESSDepreciation"]
        
        # 4. Profit Calculation
        # Base includes inverter cost normalized by duration and ILR
        profit_base = (
            li_ion_cells
            + cfg["BatteryPacks"]
            + cfg["Enclosure"]
            + cfg["BidirectionalInverter"] / (battery_duration * ilr)
            + labor
            + electricity
            + depreciation
            + cfg["MaintenanceCost"]
        )
        profit = cfg["ESSProfit"] * profit_base

        # 5. Final adjustments
        shipping = cfg["ShippingCost"] * cfg["ESSWeight"]
        passthrough = -1 * cfg["45XPassthrough"] * cfg["Battery45X"]

        breakdown = {
            "li_ion_cells": li_ion_cells,
            "battery_packs": cfg["BatteryPacks"],
            "enclosure": cfg["Enclosure"],
            "labor": labor,
            "electricity": electricity,
            "depreciation": depreciation,
            "maintenance": cfg["MaintenanceCost"],
            "profit": profit,
            "shipping": shipping,
            "passthrough_credit": passthrough
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_li_ion_cost_per_kwh"] = sum(breakdown.values())
        
        return breakdown

    def calculate_li_ion_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_li_ion_cost_breakdown()
        return breakdown["total_li_ion_cost_per_kwh"]
    
    
    def get_bi_directional_inverter_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config
        
        battery_duration = cfg["BatteryDuration"]
        ilr = cfg["ESS_ILR"]

        # 1. bi directional inverter
        bi_directional_inverter = cfg["BidirectionalInverter"] / (battery_duration * ilr)
        
        breakdown = {
            "bi_directional_inverter": bi_directional_inverter
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_bi_directional_inverter_per_kwh"] = sum(breakdown.values())
        
        return breakdown
    
    def calculate_bi_directional_inverter_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_bi_directional_inverter_cost_breakdown()
        return breakdown["total_bi_directional_inverter_per_kwh"]
    
    def get_sbos_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config
        
        ess_installation_area = cfg["ESSInstallationArea"]
        ess_container = cfg["ESSContainer"]
        
        concrete_pad_thickness = cfg["ConcretePadThickness"]
        concrete_density = cfg["ConcreteDensity"]

        # 1. site preparation and staging
        site_preparation_and_staging = cfg["SitePrepStaging"] * ess_installation_area / ess_container / 1000
        
        # 2. concrete pads
        concrete_pads = cfg["ConcretePads"] * concrete_pad_thickness * concrete_density * ess_installation_area / ess_container / 1000
        
        breakdown = {
            "site_preparation_and_staging": site_preparation_and_staging,
            "concrete_pads": concrete_pads
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_sbos_per_kwh"] = sum(breakdown.values())
        
        return breakdown

    def calculate_sbos_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_sbos_cost_breakdown()
        return breakdown["total_sbos_per_kwh"]
    
    def get_ebos_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config
        
        battery_duration = cfg["BatteryDuration"]
        ilr = cfg["ESS_ILR"]
        
        battery_capacity = cfg["BatteryCapacity"]       
        

        # 1. transformer
        transformer = cfg["Transformer"] / (battery_duration * ilr)
        
        # 2. switch gear
        switch_gear = cfg["SwitchGear"] / (battery_duration * ilr) * (1 + cfg["Tariff301"])
        
        # 3. conductors
        conductors = cfg["Conductors"] / (battery_duration * ilr)
        
        # 4. breaker / DC disconnect
        breaker_dc_disconnect = cfg["BreakerDC"] / (battery_duration * ilr) * (1 + cfg["Tariff301"])
        
        # 5. grounding
        grounding = cfg["Grounding"] / (battery_duration * ilr)
        
        # 6. SCADA
        scada = cfg["SCADA"] / (battery_duration * ilr)
        
        # 7. substation
        substation = cfg["Substation"] / (battery_duration * ilr) * (1 + cfg["Tariff301"])
        
        # 8. transmission
        transmission = (cfg["TransmissionCost"] / (battery_capacity/ilr*1000) + cfg["Transmission"] )/ (battery_duration * ilr)
        
        # 9. network upgrade
        network_upgrade = cfg["NetworkUpgrade"] / (battery_duration * ilr)
        
        # 10. shipping 
        shipping = cfg["EBOSShipping"] * cfg["EBOSWeight"] / (battery_duration * ilr)
        
        breakdown = {
            "transformer": transformer,
            "switch_gear": switch_gear,
            "conductors": conductors,
            "breaker_dc_disconnect": breaker_dc_disconnect,
            "grounding": grounding,
            "scada": scada,
            "substation": substation,
            "transmission": transmission,
            "network_upgrade": network_upgrade,
            "shipping": shipping
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_ebos_per_kwh"] = sum(breakdown.values())
        
        return breakdown

    def calculate_ebos_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_ebos_cost_breakdown()
        return breakdown["total_ebos_per_kwh"]
    
    
    def get_installation_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config
        
        ess_installation_area = cfg["ESSInstallationArea"]
        ess_container = cfg["ESSContainer"]

        # 1. installation
        installation = cfg["ESSInstallHourlyLabor"] * cfg["ESSInstallLabor"] * (1 + cfg["LaborBurdenRate"]) * ess_installation_area / ess_container / 1000
        
        breakdown = {
            "installation": installation 
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_installation_per_kwh"] = sum(breakdown.values())
        
        return breakdown
    
    def calculate_installation_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_installation_cost_breakdown()
        return breakdown["total_installation_per_kwh"]
    
    def get_permitting_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config
        
        battery_duration = cfg["BatteryDuration"]
        ilr = cfg["ESS_ILR"]

        # 1. permitting
        permitting = cfg["Permits"] / cfg["AnnualEPCInstallation"]
        
        breakdown = {
            "permitting": permitting
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_permitting_per_kwh"] = sum(breakdown.values())
        
        return breakdown
    
    def calculate_permitting_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_permitting_cost_breakdown()
        return breakdown["total_permitting_per_kwh"]
    
    
    def get_interconnection_cost_breakdown(self):
        """Returns a detailed dictionary of cost components per kWh_cap."""
        cfg = self.config
        
        battery_duration = cfg["BatteryDuration"]
        ilr = cfg["ESS_ILR"]

        # 1. interconnection
        interconnection = (cfg["InterconnectFixed"] / cfg["AnnualEPCInstallation"] + cfg["Interconnect"] / ( battery_duration * ilr) )
        
        breakdown = {
            "interconnection": interconnection
        }
        
        # Add a calculated total to the breakdown for convenience
        breakdown["total_interconnection_per_kwh"] = sum(breakdown.values())
        
        return breakdown
    
    def calculate_interconnection_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_interconnection_cost_breakdown()
        return breakdown["total_interconnection_per_kwh"]
    
    def get_sales_tax_cost_breakdown(self):
        """Returns sales tax based on Li-Ion, Inverter, sBOS, and eBOS totals."""
        cfg = self.config
        
        # Sum the specific components requested
        # We use the calculate_ wrappers to get the numeric totals ($/kWh)
        taxable_total = (
            self.calculate_li_ion_cost_per_kwh() + 
            self.calculate_bi_directional_inverter_cost_per_kwh() + 
            self.calculate_sbos_cost_per_kwh() + 
            self.calculate_ebos_cost_per_kwh()
        )

        sales_tax = taxable_total * cfg["SalesTaxRate"]

        breakdown = {
            "sales_tax": sales_tax
        }
        
        # Total for convenience
        breakdown["total_sales_tax_per_kwh"] = sales_tax
        
        return breakdown

    def calculate_sales_tax_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value."""
        breakdown = self.get_sales_tax_cost_breakdown()
        return breakdown["total_sales_tax_per_kwh"]
    
    
    def get_contingency_cost_breakdown(self):
        """Returns the contingency breakdown based on the sum of core project costs."""
        cfg = self.config
        
        # Aggregate the basis for contingency calculation ($/kWh)
        # Includes: Li-Ion, Inverter, sBOS, and eBOS
        cost_basis = (
            self.calculate_li_ion_cost_per_kwh() + 
            self.calculate_bi_directional_inverter_cost_per_kwh() + 
            self.calculate_sbos_cost_per_kwh() + 
            self.calculate_ebos_cost_per_kwh()
        )

        # Apply the contingency rate
        contingency = cost_basis * cfg["ContingencyRate"]

        breakdown = {
            "contingency": contingency
        }
        
        # Add a calculated total for convenience
        breakdown["total_contingency_per_kwh"] = contingency
        
        return breakdown

    def calculate_contingency_cost_per_kwh(self):
        """Utility wrapper that returns just the final numeric value for Contingency."""
        breakdown = self.get_contingency_cost_breakdown()
        return breakdown["total_contingency_per_kwh"]