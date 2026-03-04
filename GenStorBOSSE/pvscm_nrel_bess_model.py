# genstorbosse/pvscm_nrel_bess_model.py
import copy
import pandas as pd
from pathlib import Path
import yaml

DEFAULTS = {
    # 0. Project Parameters
    "BatteryCapacity": 60,         # MW_cap
    "BatteryDuration": 4,          # hours
    "ESS_ILR": 1,
    "AnnualESSProduction": 1_000_000,
    "AnnualEPCInstallation": 600_000,

    # 1. Li-Ion Battery Cabinets
    "LiIonCells": 75.0,            # $/kWh-cap
    "GeneralDuty": 0.034,          # %/100
    "Tariff301": 0.25,             # %/100
    "BatteryPacks": 25.0,          # $/kWh-cap
    "Enclosure": 20.0,             # $/kWh-cap
    "LaborCost": 2_500_000,        # Total plant labor $
    "LaborRate": 34.0,             # $/hour
    "ESSLabor": 0.22,              # hours/kWh_cap
    "ElectricityCost": 0.08,       # $/kWh
    "ESSElectricity": 30.5,        # kWh/kWh_cap
    "DepreciationCost": 7.0,       # $/kWh-cap/yr
    "ESSDepreciation": 0.11,       # %/100
    "MaintenanceCost": 0.28,       # $/kWh
    "ESSProfit": 0.25,             # %/100
    "ShippingCost": 1.0,           # $/kg
    "ESSWeight": 9.4,              # kg/kWh_cap
    "Battery45X": 10,              # $/kWh credit
    "45XPassthrough": 0.5,         # %/100 share

    # 2. Bi-directional Inverter
    "BidirectionalInverter": 100.0, # $/kWac

    # 3. SBOS (Structural Balance of System)
    "SitePrepStaging": 50.0,       # $/unit
    "ConcretePads": 0.10,          # $/kg
    "ESSInstallationArea": 80,     # m2/container
    "ESSContainer": 3,             # MWh/container
    "ConcretePadThickness": 0.5,   # m
    "ConcreteDensity": 2400,       # kg/m3

    # 4. EBOS (Electrical Balance of System)
    "Transformer": 40.0,           # $/kWac
    "SwitchGear": 6.5,             # $/kWac
    "Conductors": 21.0,            # $/kWac
    "BreakerDC": 15.0,             # $/kWac
    "Grounding": 9.5,              # $/kWac
    "SCADA": 3.5,                  # $/kWac
    "Substation": 33.0,            # $/kWac
    "TransmissionCost": 680_000,   # Fixed $
    "Transmission": 17.0,          # $/kWac
    "NetworkUpgrade": 0.0,         # $/kWac
    "EBOSShipping": 1.2,           # $/kg
    "EBOSWeight": 2,               # kg/kWac

    # 5. Installation
    "ESSInstallHourlyLabor": 27.5, # $/h
    "ESSInstallLabor": 2.15,       # hours/kWh_cap
    "LaborBurdenRate": 0.54,       # %/100

    # 6. Permitting
    "Permits": 200_000,            # Fixed $

    # 7. Interconnection
    "InterconnectFixed": 85_000,   # Fixed $
    "Interconnect": 35.0,          # Variable $/unit

    # 8. Sales Tax
    "SalesTaxRate": 0.058,         # %/100

    # 9. Contingency
    "ContingencyRate": 0.025,      # %/100

    # 10. EPC Overhead
    "Warehousing": 1.1,            # $/m2 
    "Logistics": 0.1,              # $/kg
    "Engineering": 3.0,            # $/m2 
    "EngineeringFixed": 50_000,    # Fixed $
    "Outreach": 1.0,               # $/m2
    "OutreachFixed": 200_000,      # Fixed $
    "ManagementFixed": 1_000_000,  # Fixed $
    "OverheadRate": 0.01,          # %/100

    # 11. Developer Profit
    "DeveloperProfit": 0.05        # %/100
}

class GenStorBOSSEModel:
    def __init__(self, user_config: dict = None):
        # This line does exactly what you asked: 
        # It takes DEFAULTS and overwrites only the keys found in user_config.
        self.config = {**DEFAULTS, **(user_config or {})}
        
        cfg = self.config
        self.dur_ilr = cfg["BatteryDuration"] * cfg["ESS_ILR"]
        self.area_per_mwh = cfg["ESSInstallationArea"] / cfg["ESSContainer"] / 1000

    @classmethod
    def from_config_file(cls, file_name: str):
        from pathlib import Path
        import json

        # 1. Starting point: where model.py lives
        base_dir = Path(__file__).parent.absolute()
        
        # 2. Define potential locations to search
        search_paths = [
            base_dir / file_name,                        # Same folder as model.py
            base_dir / "configs" / file_name,             # In a subfolder called configs
            base_dir.parent.parent / "configs" / file_name # In the parallel configs folder
        ]

        full_path = None
        for p in search_paths:
            if p.exists():
                full_path = p
                break
        
        # 3. Final fallback: try the literal string provided
        if not full_path:
            full_path = Path(file_name)

        if not full_path.exists():
            # Provide a very clear error message showing where we looked
            tried = "\n".join([str(p) for p in search_paths])
            raise FileNotFoundError(f"Could not find {file_name}. Checked:\n{tried}")

        # ... (rest of your loading logic for JSON/YAML)

        with open(full_path, 'r') as f:
            if full_path.suffix == '.json':
                data = json.load(f)
            elif full_path.suffix in ['.yaml', '.yml']:
                import yaml
                data = yaml.safe_load(f)
            else:
                raise ValueError("Unsupported file format. Use .json or .yaml")
        
        return cls(user_config=data)

    @property
    def core_basis(self):
        """The common sum used for Tax, Contingency, and Profit."""
        return (self.calculate_li_ion_cost_per_kwh() + 
                self.calculate_bi_directional_inverter_cost_per_kwh() + 
                self.calculate_sbos_cost_per_kwh() + 
                self.calculate_ebos_cost_per_kwh())

    def get_li_ion_cost_breakdown(self):
        cfg = self.config
        cells = cfg["LiIonCells"] * (1 + cfg["GeneralDuty"] + cfg["Tariff301"])
        labor = (cfg["LaborCost"] / cfg["AnnualESSProduction"]) + (cfg["LaborRate"] * cfg["ESSLabor"])
        elec = cfg["ElectricityCost"] * cfg["ESSElectricity"]
        depr = cfg["DepreciationCost"] * cfg["ESSDepreciation"]
        
        # Profit base includes inverter normalized by duration/ilr
        p_base = cells + cfg["BatteryPacks"] + cfg["Enclosure"] + (cfg["BidirectionalInverter"]/self.dur_ilr) + labor + elec + depr + cfg["MaintenanceCost"]
        
        res = {
            "li_ion_cells": cells, "battery_packs": cfg["BatteryPacks"], "enclosure": cfg["Enclosure"],
            "labor": labor, "electricity": elec, "depreciation": depr, "maintenance": cfg["MaintenanceCost"],
            "profit": cfg["ESSProfit"] * p_base, "shipping": cfg["ShippingCost"] * cfg["ESSWeight"],
            "passthrough_credit": -cfg["45XPassthrough"] * cfg["Battery45X"]
        }
        res["total_li_ion_cost_per_kwh"] = sum(res.values())
        return res

    def get_bi_directional_inverter_cost_breakdown(self):
        val = self.config["BidirectionalInverter"] / self.dur_ilr
        return {"bi_directional_inverter": val, "total_bi_directional_inverter_per_kwh": val}

    def get_sbos_cost_breakdown(self):
        cfg = self.config
        prep = cfg["SitePrepStaging"] * self.area_per_mwh
        pads = cfg["ConcretePads"] * cfg["ConcretePadThickness"] * cfg["ConcreteDensity"] * self.area_per_mwh
        return {"site_prep": prep, "concrete_pads": pads, "total_sbos_per_kwh": prep + pads}

    def get_ebos_cost_breakdown(self):
        cfg, d_i = self.config, self.dur_ilr
        t301 = 1 + cfg["Tariff301"]
        
        res = {
            "transformer": cfg["Transformer"] / d_i,
            "switch_gear": (cfg["SwitchGear"] / d_i) * t301,
            "conductors": cfg["Conductors"] / d_i,
            "breaker_dc": (cfg["BreakerDC"] / d_i) * t301,
            "grounding": cfg["Grounding"] / d_i,
            "scada": cfg["SCADA"] / d_i,
            "substation": (cfg["Substation"] / d_i) * t301,
            "transmission": (cfg.get("TransmissionCost", 0) / (cfg["BatteryCapacity"] / cfg["ESS_ILR"] * 1000) + cfg["Transmission"]) / d_i,
            "network_upgrade": cfg["NetworkUpgrade"] / d_i,
            "shipping": (cfg["EBOSShipping"] * cfg["EBOSWeight"]) / d_i
        }
        res["total_ebos_per_kwh"] = sum(res.values())
        return res

    def get_installation_cost_breakdown(self):
        val = self.config["ESSInstallHourlyLabor"] * self.config["ESSInstallLabor"] * (1 + self.config["LaborBurdenRate"]) * self.area_per_mwh
        return {"installation": val, "total_installation_per_kwh": val}

    def get_permitting_cost_breakdown(self):
        val = self.config["Permits"] / self.config["AnnualEPCInstallation"]
        return {"permitting": val, "total_permitting_per_kwh": val}

    def get_interconnection_cost_breakdown(self):
        val = (self.config["InterconnectFixed"] / self.config["AnnualEPCInstallation"]) + (self.config["Interconnect"] / self.dur_ilr)
        return {"interconnection": val, "total_interconnection_per_kwh": val}

    # Streamlined wrapper logic for repetitive "Basis * Rate" functions
    def _basis_rate_calc(self, rate_key, total_key, label):
        val = self.core_basis * self.config[rate_key]
        return {label: val, total_key: val}

    def get_sales_tax_cost_breakdown(self): return self._basis_rate_calc("SalesTaxRate", "total_sales_tax_per_kwh", "sales_tax")
    def get_contingency_cost_breakdown(self): return self._basis_rate_calc("ContingencyRate", "total_contingency_per_kwh", "contingency")
    def get_profit_cost_breakdown(self): return self._basis_rate_calc("DeveloperProfit", "total_profit_per_kwh", "profit")

    def get_epc_overhead_cost_breakdown(self):
        cfg, a_m = self.config, self.area_per_mwh
        ann = cfg["AnnualEPCInstallation"]
        res = {
            "warehousing": cfg["Warehousing"] * a_m,
            "logistics": cfg["Logistics"] * cfg["ESSWeight"],
            "engineering": (cfg["EngineeringFixed"] / ann) + (cfg["Engineering"] * a_m),
            "outreach": (cfg["OutreachFixed"] / ann) + (cfg["Outreach"] * a_m),
            "management": (cfg["ManagementFixed"] / ann) + (cfg["OverheadRate"] * self.core_basis)
        }
        res["total_epc_overhead_per_kwh"] = sum(res.values())
        return res

    # Logic to generate all calculate_X methods dynamically to save 50+ lines of code
    def __getattr__(self, name):
        if name.startswith("calculate_") and name.endswith("_per_kwh"):
            target_getter = "get_" + name[10:-8] + "_breakdown"
            if hasattr(self, target_getter):
                breakdown = getattr(self, target_getter)()
                return lambda: breakdown[next(k for k in breakdown if k.startswith("total_"))]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get_cost_breakdown(self, higher_resolution=False):
        subsystems = {
            "li_ion": self.get_li_ion_cost_breakdown, "inverter": self.get_bi_directional_inverter_cost_breakdown,
            "sbos": self.get_sbos_cost_breakdown, "ebos": self.get_ebos_cost_breakdown,
            "installation": self.get_installation_cost_breakdown, "permitting": self.get_permitting_cost_breakdown,
            "interconnection": self.get_interconnection_cost_breakdown, "sales_tax": self.get_sales_tax_cost_breakdown,
            "contingency": self.get_contingency_cost_breakdown, "epc_overhead": self.get_epc_overhead_cost_breakdown,
            "developer_profit": self.get_profit_cost_breakdown
        }
        output, total = {}, 0.0
        for name, func in subsystems.items():
            sub = func()
            val = sub[next(k for k in sub if k.startswith("total_"))]
            total += val
            output[name] = {"total": val, "components": {k: v for k, v in sub.items() if not k.startswith("total_")}} if higher_resolution else val
        output["total_project_cost_per_kwh"] = total
        return output