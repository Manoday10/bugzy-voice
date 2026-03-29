"""
Product Specific Validator Module

This module contains product-specific information and validation logic
for The Good Bug health chatbot products.
"""

from typing import Dict, Any, List, Optional


class ProductSpecificValidator:
    def __init__(self):
        self.known_compositions = {
            "Metabolically Lean AMS": {
                "confirmed_ingredients": [
                    "multistrain probiotics (Lactobacillus, Bifidobacterium)",
                    "prebiotic fiber (7g per serving)",
                    "l-carnitine",
                    "chromium picolinate"
                ],
                "confirmed_not_included": ["digestive enzymes"],
                "fiber_amount": "7g per 8g scoop",
                "cfu_count": "16 billion CFUs per sachet",
                "dosage": "1 sachet probiotics + 1 scoop fiber in 200ml water, once daily",
                "timing": "Shortly before or between main meals (lunch/dinner)",
                "benefits": [
                    "Supports weight loss",
                    "Reduces BMI, waist and hip circumference",
                    "Improves metabolic health markers",
                    "92.19% reduction in bloating",
                    "91.67% reduction in acidity",
                    "90% improvement in bowel movements"
                ],
                "contraindications": ["Check if pregnant/lactating", "Consult doctor if on diabetes medications"]
            },
            "Metabolically Lean Supercharged": {
                "confirmed_ingredients": [
                    "multistrain Lactobacillus & Bifidobacterium probiotics",
                    "prebiotics (inulin)",
                    "L-Carnitine",
                    "Chromium"
                ],
                "dosage": "1 sachet daily",
                "timing": "After meal",
                "benefits": ["Boosts metabolism", "Curbs cravings", "Aids weight loss"]
            },
            "PCOS Balance": {
                "confirmed_ingredients": [
                    "Myo-inositol",
                    "D-chiro-inositol",
                    "Multiple probiotic strains",
                    "Magnesium (as flow agent)"
                ],
                "sweeteners": ["Sorbitol", "Xylitol"],
                "dosage": "Mix in 200ml water or take directly",
                "timing": "30 minutes after any major meal",
                "benefits": [
                    "Regulates menstrual cycles",
                    "Restores hormonal balance",
                    "Reduces testosterone and insulin resistance",
                    "Improves mental health",
                    "Reduces acne and facial hair growth"
                ]
            },
            "Gut Balance": {
                "confirmed_ingredients": [
                    "Lacticaseibacillus rhamnosus GG",
                    "Bifidobacterium animalis subsp. lactis",
                    "Inulin (prebiotic fiber)",
                    "Vitamin C",
                    "Digestive enzyme blend"
                ],
                "enzyme_types": ["Alpha-amylase", "Cellulase", "Lipase", "Lactase", "Protease"],
                "dosage": "1 stick daily (tear & gulp)",
                "timing": "After a meal (breakfast, lunch, or dinner)",
                "benefits": [
                    "Reduces bloating, gas, acidity",
                    "Improves digestion",
                    "Strengthens immunity",
                    "Better nutrient absorption"
                ]
            },
            "Bye Bye Bloat": {
                "confirmed_ingredients": ["Bifidobacterium Longum W11", "Digestive enzymes"],
                "sweetener": "Sorbitol (sugar-free prebiotic)",
                "dosage": "1 sachet daily",
                "timing": "Any time of day",
                "benefits": ["Reduces bloating", "Eases abdominal pain", "Improves metabolism"]
            },
            "Smooth Move": {
                "confirmed_ingredients": [
                    "Probiotics (Bifidobacterium)",
                    "Inulin (soluble fiber)",
                    "Magnesium"
                ],
                "sweeteners": ["Mannitol", "Sorbitol", "Stevia"],
                "dosage": "1 sachet in 200ml water",
                "timing": "Post dinner or bedtime",
                "benefits": ["Relieves constipation", "Softens stool", "Induces peristalsis", "Not habit-forming"],
                "notes": "Results usually within 7 days, not a laxative"
            },
            "IBS Rescue": {
                "confirmed_ingredients": [
                    "Bifidobacterium Longum W11",
                    "L-Glutamine",
                    "Prebiotic fiber (controlled amount)"
                ],
                "target": "Constipation-dominant IBS (IBS-C)",
                "dosage": "Mix in 200ml water (lemon-flavoured)",
                "timing": "Once daily",
                "benefits": [
                    "Regularizes bowel movements",
                    "Relieves chronic constipation",
                    "Reduces bloating, gas, abdominal discomfort",
                    "Soothes stress-sensitive gut",
                    "Relaxes muscles and provides pain relief"
                ]
            },
            "IBS DnM": {
                "confirmed_ingredients": [
                    "Lactobacillus rhamnosus GG",
                    "Saccharomyces boulardii CNCM I-3799"
                ],
                "target": "Diarrhea-dominant or mixed IBS (IBS-D & IBS-M)",
                "dosage": "Tear sachet, mix in room temperature water",
                "timing": "Once daily",
                "benefits": [
                    "Regulates both diarrhea and constipation",
                    "Reduces gut stress",
                    "Antimicrobial and anti-inflammatory effects",
                    "Eases abdominal pain, burping, stomach gas"
                ]
            },
            "First Defense": {
                "type": "Synbiotic (probiotics + prebiotics + nutrients)",
                "confirmed_ingredients": ["Probiotics", "Prebiotics", "Immune-supporting nutrients"],
                "dosage": "1 stick daily",
                "timing": "After meal",
                "age_limit": "18 years and above",
                "benefits": [
                    "Strengthens immune system",
                    "Provides barrier against pathogens",
                    "Better nutrient absorption",
                    "Reduces flu and infections"
                ]
            },
            "Sleep and Calm": {
                "confirmed_ingredients": ["L. reuteri (probiotic)", "Melatonin", "L-theanine", "Magnesium"],
                "dosage": "1 stick daily",
                "timing": "Before bedtime",
                "benefits": [
                    "Improves sleep quality",
                    "Reduces anxiety and stress",
                    "Promotes relaxation",
                    "Regulates sleep-wake cycle"
                ],
                "warnings": [
                    "Do not take with blood thinners",
                    "Contains Melatonin - consult doctor if on blood thinners or anti-anxiety medications"
                ]
            },
            "Good Down There": {
                "confirmed_ingredients": ["Blend of Lactobacillus strains", "Cranberry extract", "D-Mannose"],
                "dosage": "1 stick daily",
                "timing": "30 minutes after substantial meal",
                "benefits": [
                    "Supports vaginal health",
                    "Combats UTIs",
                    "Reduces infections and discharge",
                    "Promotes healthy vaginal flora"
                ],
                "notes": "D-Mannose is safe for diabetics (doesn't convert to glucose)"
            },
            "Good to Glow": {
                "confirmed_ingredients": [
                    "Lactobacillus plantarum", "Glutathione", "Lycopene", "Resveratrol",
                    "Vitamin A", "Biotin", "Zinc", "Vitamin C"
                ],
                "dosage": "1 stick daily",
                "timing": "30 minutes after meals",
                "benefits": [
                    "Stimulates collagen",
                    "Brightens skin and reduces pigmentation",
                    "Antioxidant properties",
                    "Improves skin, hair, and nails",
                    "Reduces wrinkles after 3 months"
                ],
                "notes": "Visible results within 4 weeks"
            },
            "Happy Tummies": {
                "confirmed_ingredients": ["Probiotics", "Vitamins"],
                "age_range": "3 years and above",
                "dosage": "1 stick daily",
                "timing": "Any time",
                "benefits": [
                    "Improves children's digestion",
                    "Helps with loose motions and stomach pain",
                    "Enhances immunity (70% immune system in gut)",
                    "Increases energy levels",
                    "Maintains healthy weight"
                ]
            },
            "Acidity Aid": {
                "confirmed_ingredients": [
                    "Lactobacillus Gasseri", "Bifidobacterium Bifidum", "Inulin",
                    "Digestive enzymes", "Amla extract", "Liquorice extract"
                ],
                "dosage": "1 sachet daily",
                "timing": "After main meal (1 hour gap if taking other antacids)",
                "benefits": [
                    "Eases acidity, heartburn, indigestion",
                    "Stimulates good bacteria growth",
                    "Aids digestion",
                    "Improves gut barrier function",
                    "Maintains healthy gut pH"
                ]
            },
            "Gut Cleanse": {
                "type": "14-day prebiotic colon detox shot",
                "confirmed_ingredients": [
                    "Fructooligosaccharide (FOS)", "Triphala (Amla, Baheda, Harad)",
                    "Kokum", "Fenugreek extract", "Cumin extract", "Rosemary extract", "Green Tea"
                ],
                "preservative": "Sodium Benzoate (class 2)",
                "dosage": "1 shot daily for 14 days",
                "timing": "First thing in the morning on empty stomach",
                "benefits": [
                    "Detoxifies and cleanses colon",
                    "Flushes out toxins and waste",
                    "Reduces bloating",
                    "Improves digestion",
                    "Healthier skin",
                    "Enhanced energy levels"
                ],
                "warnings": [
                    "Contains Fenugreek - diabetics consult doctor",
                    "Not for pregnant/lactating women, IBS D&M patients",
                    "Wait 40-45 min before eating after consumption"
                ]
            },
            "Metabolic Fiber Boost": {
                "confirmed_ingredients": [
                    "Wheat dextrin", "Glucomannan", "Chromium Picolinate", "Fructo-oligosaccharides (FOS)"
                ],
                "fiber_amount": "7g per scoop",
                "dosage": "Start with 1/2 scoop for 1 week, then 1 full scoop",
                "timing": "Between main meals",
                "benefits": [
                    "Aids weight loss", "Lowers cholesterol", "Manages blood sugar",
                    "Controls appetite", "Regulates bowel movements"
                ],
                "notes": "Psyllium-free, no fillers, flavourless and odourless"
            },
            "Smooth Move Fiber Boost": {
                "confirmed_ingredients": ["Sunfiber", "Psyllium Husk", "Lactitol"],
                "fiber_amount": "5g per scoop",
                "dosage": "Start with 1/2 scoop for 1 week, then 1 full scoop",
                "timing": "40-45 minutes after dinner",
                "benefits": [
                    "Relieves constipation", "Softens and adds bulk to stool",
                    "Regulates moisture and electrolytes", "Increases satiation", "Works as gentle laxative"
                ]
            },
            "Prebiotic Fiber Boost": {
                "confirmed_ingredients": [
                    "Fructooligosaccharides (FOS)", "Inulin", "Green Pea Fiber",
                    "Galactooligosaccharides (GOS)", "Isomaltooligosaccharides (IMO)"
                ],
                "fiber_amount": "4.7g per scoop",
                "dosage": "Start with 1/2 scoop for 1 week, then 1 full scoop",
                "timing": "Between main meals",
                "benefits": [
                    "Improves bacterial diversity", "Suppresses appetite", "Improves digestion",
                    "Lowers blood sugar and cholesterol", "Reduces inflammation"
                ]
            },
            "Water Kefir": {
                "type": "Fermented probiotic beverage",
                "serving_size": "150ml daily",
                "timing": "Morning on empty stomach or midday",
                "benefits": [
                    "Rich in probiotics, B vitamins, enzymes, minerals",
                    "Improves gut health and digestion",
                    "Enhances immunity",
                    "Low-sugar, calorie-friendly alternative"
                ],
                "properties": [
                    "Dairy-free and vegan", "Caffeine-free",
                    "Contains trace alcohol (<0.5%)", "Lasts 2-3 weeks refrigerated"
                ]
            },
            "Kombucha": {
                "type": "Fermented tea with SCOBY",
                "serving_size": "300ml (1 bottle) daily",
                "timing": "With meals or afternoon pick-me-up",
                "benefits": [
                    "Improves gut health and digestion",
                    "Supports immunity",
                    "Boosts energy levels",
                    "Rich in probiotics and antioxidants"
                ],
                "properties": [
                    "Contains small amount of caffeine",
                    "Contains trace alcohol (<0.5%)",
                    "Dairy-free and vegan",
                    "Naturally fizzy and slightly tangy"
                ]
            },
            "12 Week Guided Program": {
                "type": "12 Week Guided Weight Loss Program",
                "duration": "90 days (12 weeks)",
                "confirmed_ingredients": [
                    "Metabolically Lean Probiotics (one sachet daily for 90 days)",
                    "Metabolic Fiber Boost (one serving daily for 90 days)"
                ],
                "program_includes": [
                    "Metabolically Lean Probiotics - 90 sachets",
                    "Metabolic Fiber Boost - 90 servings",
                    "1 nutritionist consultation with customized diet plan",
                    "90-day Cultpass Home membership for guided workouts",
                    "AI Health Coach access for daily guidance and tracking",
                    "SuperGut Sipper"
                ],
                "dosage": "1 sachet Metabolically Lean Probiotics + 1 serving Metabolic Fiber Boost daily",
                "timing": "Daily for 90 days",
                "benefits": [
                    "Structured 12-week guided program for sustainable weight loss",
                    "Supports gradual and sustainable weight loss",
                    "Improves metabolic health and gut health",
                    "Personalized diet plan from nutritionist",
                    "Guided workouts through Cultpass Home membership",
                    "Daily support and accountability from AI Health Coach",
                    "Long-term results through improved gut health, nutrition, and lifestyle habits"
                ],
                "notes": "A comprehensive wellness plan designed for gradual and sustainable weight loss over 90 days, combining probiotics, fiber, nutrition guidance, workouts, and AI coaching support"
            },
            "Post Meal Digestive Mints": {
                "confirmed_ingredients": [
                    "Alpha-Amylase", "Cellulase", "Lactase", 
                    "Neutral Protease", "Lipase", "Alpha-Galactosidase", "Papain"
                ],
                "dosage": "1 mint after any meal",
                "max_intake": "3 mints per day",
                "timing": "After any meal",
                "flavours": ["Peppermint", "Calcutta Paan", "Coffee"],
                "benefits": [
                    "Supports digestion",
                    "Reduces bloating, gas and heaviness",
                    "Aids better nutrient breakdown",
                    "Helps break down carbs, proteins, and fats",
                    "Neutral Protease reduces bad breath by breaking down oral proteins"
                ],
                "notes": "No water required. Simply let it dissolve in the mouth. No added sugar (uses sugar alcohols)."
            },
            "ACV with Garcinia Cambogia": {
                "confirmed_ingredients": [
                    "Apple Cider Vinegar with Mother",
                    "Garcinia Cambogia (HCA)",
                    "Gut Complex (AstraGin®, Piperine, Bacillus coagulans)",
                    "Vitamin B6",
                    "Vitamin B12"
                ],
                "dosage": "1 tablet per day, dissolved in 200ml water",
                "timing": "Before meals (though consistency matters more than timing)",
                "benefits": [
                    "Supports metabolism and appetite balance",
                    "Supports fat metabolism",
                    "Improves nutrient absorption and gut tolerance",
                    "Gentler and more bioavailable than plain ACV"
                ],
                "warnings": [
                    "Not for pregnant/lactating women",
                    "Not for individuals under 18 years of age",
                    "Diabetics consult healthcare professional",
                    "Consult professional if on diuretics, insulin, or cardiovascular medications"
                ]
            },
            "Gluta Glow": {
                "confirmed_ingredients": [
                    "Glutathione (500mg)",
                    "Hyaluronic Acid",
                    "Resveratrol",
                    "Gut Absorption Complex (AstraGin®, Piperine, Bacillus coagulans)"
                ],
                "dosage": "1 tablet in 200-250ml water",
                "timing": "Daily consistency (visible results in 8-12 weeks)",
                "benefits": [
                    "Supports skin radiance and hydration",
                    "Antioxidant support to reduce oxidative stress",
                    "Improves skin texture and provides visible glow",
                    "Supports overall skin health from within"
                ],
                "notes": "Suitable for both men and women. Vegetarian.",
                "warnings": ["Consult professional if pregnant/lactating"]
            }
        }
        
        self.product_aliases = {
            "ams": "Metabolically Lean AMS",
            "advanced metabolic system": "Metabolically Lean AMS",
            "metabolic system": "Metabolically Lean AMS",
            "metabolically lean": "Metabolically Lean AMS",
            "met lean": "Metabolically Lean AMS",
            "supercharged": "Metabolically Lean Supercharged",
            "pcos": "PCOS Balance",
            "pcod": "PCOS Balance",
            "gut balance": "Gut Balance",
            "bloat": "Bye Bye Bloat",
            "bye bye bloat": "Bye Bye Bloat",
            "smooth move": "Smooth Move",
            "constipation": "Smooth Move",
            "ibs rescue": "IBS Rescue",
            "ibs c": "IBS Rescue",
            "ibs constipation": "IBS Rescue",
            "ibs dnm": "IBS DnM",
            "ibs d&m": "IBS DnM",
            "ibs d": "IBS DnM",
            "ibs m": "IBS DnM",
            "ibs diarrhea": "IBS DnM",
            "ibs mixed": "IBS DnM",
            "first defense": "First Defense",
            "first defence": "First Defense",
            "immunity": "First Defense",
            "sleep": "Sleep and Calm",
            "sleep and calm": "Sleep and Calm",
            "good down there": "Good Down There",
            "uti": "Good Down There",
            "vaginal health": "Good Down There",
            "good to glow": "Good to Glow",
            "skin": "Good to Glow",
            "glow": "Good to Glow",
            "happy tummies": "Happy Tummies",
            "kids": "Happy Tummies",
            "acidity": "Acidity Aid",
            "acidity aid": "Acidity Aid",
            "heartburn": "Acidity Aid",
            "gut cleanse": "Gut Cleanse",
            "cleanse": "Gut Cleanse",
            "detox": "Gut Cleanse",
            "metabolic fiber": "Metabolic Fiber Boost",
            "metabolic fiber boost": "Metabolic Fiber Boost",
            "smooth fiber": "Smooth Move Fiber Boost",
            "smooth move fiber": "Smooth Move Fiber Boost",
            "prebiotic fiber": "Prebiotic Fiber Boost",
            "fiber boost": "Prebiotic Fiber Boost",
            "water kefir": "Water Kefir",
            "kefir": "Water Kefir",
            "kombucha": "Kombucha",
            "12 week guided program": "12 Week Guided Program",
            "12-week guided program": "12 Week Guided Program",
            "12 week guided": "12 Week Guided Program",
            "12-week guided": "12 Week Guided Program",
            "12 week program": "12 Week Guided Program",
            "12-week program": "12 Week Guided Program",
            "digestive mints": "Post Meal Digestive Mints",
            "digestive enzymes": "Post Meal Digestive Mints",
            "mints": "Post Meal Digestive Mints",
            "acv": "ACV with Garcinia Cambogia",
            "apple cider vinegar": "ACV with Garcinia Cambogia",
            "garcinia": "ACV with Garcinia Cambogia",
            "gluta": "Gluta Glow",
            "gluta glow": "Gluta Glow",
            "glutathione": "Gluta Glow"
        }

    def get_product_info(self, product_name: str) -> Optional[Dict[str, Any]]:
        return self.known_compositions.get(product_name)
    
    def validate_product_claim(self, product_name: str, claim_type: str) -> Dict[str, Any]:
        product_info = self.get_product_info(product_name)
        if not product_info:
            return {"validated": False, "reason": "Product not found in database"}
        return {"validated": True, "product_info": product_info, "claim_type": claim_type}
    
    def check_health_contraindications(self, product_name: str, health_context: Dict[str, Any]) -> List[str]:
        product_info = self.get_product_info(product_name)
        if not product_info:
            return []
        
        warnings = []
        
        if health_context.get("medications"):
            medications_lower = health_context["medications"].lower()
            if "blood thinner" in medications_lower or "warfarin" in medications_lower:
                if product_name == "Sleep and Calm":
                    warnings.append("⚠️ Sleep and Calm contains Melatonin - consult doctor as you're on blood thinners")
            
            if "diabetes" in medications_lower or "metformin" in medications_lower or "insulin" in medications_lower:
                if product_name == "Gut Cleanse":
                    warnings.append("⚠️ Gut Cleanse contains Fenugreek - consult doctor as you're on diabetes medications")
        
        if health_context.get("health_conditions"):
            conditions_lower = health_context["health_conditions"].lower()
            if "pregnant" in conditions_lower or "lactating" in conditions_lower or "breastfeeding" in conditions_lower:
                if product_name == "Gut Cleanse":
                    warnings.append("⚠️ Gut Cleanse is not recommended for pregnant/lactating women")
                elif product_name == "ACV with Garcinia Cambogia":
                    warnings.append("⚠️ ACV with Garcinia Cambogia is not recommended for pregnant/lactating women")
                elif product_name in ["Post Meal Digestive Mints", "Gluta Glow"]:
                    warnings.append(f"⚠️ Consult a healthcare professional before using {product_name} during pregnancy or lactation")
            
            if "diabetes" in conditions_lower or "diabetic" in conditions_lower:
                if product_name == "ACV with Garcinia Cambogia":
                    warnings.append("⚠️ Consult your healthcare professional before using ACV with Garcinia Cambogia if you have diabetes")
        
        if health_context.get("allergies"):
            allergies_lower = health_context["allergies"].lower()
            if "dairy" in allergies_lower and product_info.get("properties"):
                properties = product_info.get("properties", [])
                if "dairy-free" not in [p.lower() for p in properties]:
                    warnings.append(f"⚠️ Please verify if {product_name} is suitable for your dairy allergy")
        
        return warnings


def get_canonical_product_names_from_order(order_str: Optional[str]) -> List[str]:
    """
    Parse CRM order string and return only canonical main product names
    (from product_aliases). Used for greeting text and products_accessed.

    Examples:
        "Bye Bye Bloat | Soothes Bloating - 15 Days, Bugsy | Your AI Gut Coach"
        -> ["Bye Bye Bloat"]   (Bugsy not in alias list)
        "Metabolically lean | Weight Management Support" -> ["Metabolically Lean AMS"]
    """
    if not order_str or not isinstance(order_str, str):
        return []
    v = ProductSpecificValidator()
    aliases = v.product_aliases
    # Match longest alias first so "bye bye bloat" matches before "bloat"
    sorted_keys = sorted(aliases.keys(), key=len, reverse=True)
    result = []
    seen = set()
    for segment in order_str.split(","):
        segment = segment.strip()
        if not segment:
            continue
        part = segment.split("|", 1)[0].strip() if "|" in segment else segment
        part_lower = part.lower()
        for key in sorted_keys:
            if key in part_lower:
                canonical = aliases[key]
                if canonical not in seen:
                    seen.add(canonical)
                    result.append(canonical)
                break
    return result
