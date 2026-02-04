#!/usr/bin/env python3
"""
Create the Oropharyngeal Cancer Algorithmic Staging Case

This script creates a comprehensive case document that guides radiologists
through a systematic approach to reporting oropharyngeal cancer staging scans.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, db
from models import Case, CaseStatus, BodyPart, FRCRModule, AgeGroup

# The algorithmic discussion content
DISCUSSION_HTML = """
<div class="algorithm-guide" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">

<!-- Header Banner -->
<div style="background: linear-gradient(135deg, #5E899E 0%, #4a7285 100%); color: white; padding: 25px; border-radius: 8px; margin-bottom: 25px;">
    <h2 style="margin: 0 0 10px 0; font-size: 1.5rem;">Oropharyngeal Cancer Staging Algorithm</h2>
    <p style="margin: 0; opacity: 0.95;">A systematic approach to CT/MRI staging based on AJCC 8th Edition</p>
</div>

<!-- Quick Reference Card -->
<div style="background: #fff; border: 2px solid #e96304; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
    <h3 style="color: #e96304; margin-top: 0; display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 1.2em;">⚡</span> Quick Reference - Mnemonics
    </h3>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
        <!-- T4b Mnemonic -->
        <div style="background: #ffebee; border-radius: 6px; padding: 15px;">
            <h4 style="color: #c62828; margin: 0 0 10px 0;">T4b = "PACE" (Unresectable)</h4>
            <div style="display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #c62828; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">P</span>
                    <span>revertebral fascia invasion</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #c62828; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">A</span>
                    <span>rtery (carotid encasement &gt;270°)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #c62828; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">C</span>
                    <span>ranium (skull base invasion)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #c62828; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">E</span>
                    <span>xtension (mediastinal)</span>
                </div>
            </div>
        </div>

        <!-- T4a Mnemonic -->
        <div style="background: #fff3e0; border-radius: 6px; padding: 15px;">
            <h4 style="color: #e65100; margin: 0 0 10px 0;">T4a = "HELP-M" (Advanced Resectable)</h4>
            <div style="display: flex; flex-direction: column; gap: 6px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #e65100; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">H</span>
                    <span>ard palate</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #e65100; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">E</span>
                    <span>xtrinsic tongue muscles</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #e65100; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">L</span>
                    <span>arynx invasion</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #e65100; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">P</span>
                    <span>terygoid (medial muscle)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #e65100; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">M</span>
                    <span>andible</span>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Step-by-Step Algorithm -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
    <h3 style="color: #2c3e50; margin-top: 0;">
        <span style="color: #5E899E;">📋</span> Systematic Staging Algorithm
    </h3>

    <!-- Step 1: HPV Status -->
    <div style="background: white; border-left: 4px solid #5E899E; padding: 15px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #5E899E; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">1</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Check HPV/p16 Status FIRST</h4>
                <p style="margin: 0 0 10px 0; color: #5a6270;">Different staging systems apply! HPV+ has better prognosis and simpler N staging.</p>
                <div style="background: #fff3cd; border-left: 3px solid #ffc107; padding: 10px; border-radius: 4px;">
                    <strong style="color: #856404;">⚠️ Key Point:</strong>
                    <span style="color: #856404;">If HPV status unknown, treat as HPV-negative for staging purposes.</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Step 2: Rule Out T4b -->
    <div style="background: white; border-left: 4px solid #dc3545; padding: 15px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #dc3545; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">2</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Rule Out T4b (Unresectable) - "PACE"</h4>
                <p style="margin: 0 0 10px 0; color: #5a6270;">Check these features first as they indicate unresectable disease:</p>
                <ul style="margin: 0; padding-left: 20px; color: #5a6270;">
                    <li><strong>Prevertebral fascia:</strong> Look for obliteration of retropharyngeal fat</li>
                    <li><strong>Carotid encasement:</strong> Must be &gt;270° (not just contact!)</li>
                    <li><strong>Skull base:</strong> Check clivus, pterygoid plates on bone windows</li>
                    <li><strong>Mediastinum:</strong> Extension below thoracic inlet</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Step 3: Check T4a -->
    <div style="background: white; border-left: 4px solid #e96304; padding: 15px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #e96304; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">3</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Check T4a Features - "HELP-M"</h4>
                <p style="margin: 0 0 10px 0; color: #5a6270;">If no T4b, check for T4a (advanced but resectable):</p>
                <ul style="margin: 0; padding-left: 20px; color: #5a6270;">
                    <li><strong>Hard palate:</strong> Cortical erosion or invasion</li>
                    <li><strong>Extrinsic tongue muscles:</strong> Genioglossus, hyoglossus, styloglossus (NOT intrinsic!)</li>
                    <li><strong>Larynx:</strong> Epiglottis, arytenoids, or cartilage invasion</li>
                    <li><strong>Medial pterygoid:</strong> Muscle infiltration</li>
                    <li><strong>Mandible:</strong> Cortical erosion or invasion</li>
                </ul>
            </div>
        </div>
    </div>

    <!-- Step 4: Measure Tumor -->
    <div style="background: white; border-left: 4px solid #28a745; padding: 15px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #28a745; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">4</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Measure Tumor Size</h4>
                <p style="margin: 0 0 10px 0; color: #5a6270;">If no T4 features, size determines T stage:</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr style="background: #5E899E; color: white;">
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Size</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">T Stage</th>
                    </tr>
                    <tr style="background: #f8f9fa;">
                        <td style="padding: 8px; border: 1px solid #ddd;">≤2 cm</td>
                        <td style="padding: 8px; text-align: center; border: 1px solid #ddd;"><strong>T1</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;">&gt;2 cm to ≤4 cm</td>
                        <td style="padding: 8px; text-align: center; border: 1px solid #ddd;"><strong>T2</strong></td>
                    </tr>
                    <tr style="background: #f8f9fa;">
                        <td style="padding: 8px; border: 1px solid #ddd;">&gt;4 cm OR lingual epiglottis (HPV- only)</td>
                        <td style="padding: 8px; text-align: center; border: 1px solid #ddd;"><strong>T3</strong></td>
                    </tr>
                </table>
            </div>
        </div>
    </div>

    <!-- Step 5: Nodal Assessment -->
    <div style="background: white; border-left: 4px solid #6f42c1; padding: 15px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #6f42c1; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">5</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Systematic Nodal Survey</h4>
                <p style="margin: 0 0 10px 0; color: #5a6270;">Check ALL levels including retropharyngeal nodes:</p>
                <ul style="margin: 0; padding-left: 20px; color: #5a6270;">
                    <li>Measure <strong>SHORT AXIS</strong> (perpendicular to long axis)</li>
                    <li>Count ipsilateral vs contralateral nodes</li>
                    <li>Note largest node size</li>
                    <li>Look for <strong>ENE</strong>: irregular margins, fat infiltration, matted nodes</li>
                </ul>
                <div style="background: #e8f5e9; border-left: 3px solid #28a745; padding: 10px; margin-top: 10px; border-radius: 4px;">
                    <strong style="color: #2e7d32;">💡 Remember:</strong>
                    <span style="color: #2e7d32;">ENE changes N stage only for HPV-negative disease!</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Step 6: Check Mets -->
    <div style="background: white; border-left: 4px solid #17a2b8; padding: 15px; margin-bottom: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #17a2b8; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">6</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Check for Distant Metastases</h4>
                <p style="margin: 0; color: #5a6270;">Review visible lungs, liver, and bones on the current study. M1 = Stage IVC.</p>
            </div>
        </div>
    </div>

    <!-- Step 7: Calculate Stage -->
    <div style="background: white; border-left: 4px solid #ffc107; padding: 15px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <span style="background: #ffc107; color: #2c3e50; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">7</span>
            <div style="flex: 1;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">Calculate Overall Stage</h4>
                <p style="margin: 0; color: #5a6270;">Use the embedded TNM Calculator below to combine T, N, M into overall stage group.</p>
            </div>
        </div>
    </div>
</div>

<!-- N Staging Comparison -->
<div style="background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
    <h3 style="color: #2c3e50; margin-top: 0;">
        <span style="color: #5E899E;">📊</span> N Staging: HPV+ vs HPV- Comparison
    </h3>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
        <!-- HPV+ Column -->
        <div style="background: #e8f5e9; border-radius: 8px; padding: 15px;">
            <h4 style="background: #28a745; color: white; padding: 10px; border-radius: 6px; margin: -15px -15px 15px -15px; text-align: center;">HPV-Positive (Simpler)</h4>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #28a745;">
                    <strong>N0:</strong> No nodes
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #28a745;">
                    <strong>N1:</strong> Ipsilateral nodes, all ≤6 cm
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #28a745;">
                    <strong>N2:</strong> Bilateral/contralateral, all ≤6 cm
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #28a745;">
                    <strong>N3:</strong> Any node &gt;6 cm
                </div>
            </div>
            <div style="background: #fff3cd; padding: 10px; border-radius: 4px; margin-top: 10px; font-size: 0.9em;">
                <strong>Note:</strong> ENE doesn't change N stage for HPV+
            </div>
        </div>

        <!-- HPV- Column -->
        <div style="background: #ffebee; border-radius: 8px; padding: 15px;">
            <h4 style="background: #dc3545; color: white; padding: 10px; border-radius: 6px; margin: -15px -15px 15px -15px; text-align: center;">HPV-Negative (Complex)</h4>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N0:</strong> No nodes
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N1:</strong> Single ipsilateral ≤3 cm, no ENE
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N2a:</strong> Single ipsi &gt;3-6 cm, no ENE
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N2b:</strong> Multiple ipsi ≤6 cm, no ENE
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N2c:</strong> Bilateral/contra ≤6 cm, no ENE
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N3a:</strong> Any node with clinical ENE
                </div>
                <div style="background: white; padding: 10px; border-radius: 4px; border-left: 3px solid #dc3545;">
                    <strong>N3b:</strong> Any node &gt;6 cm
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Common Pitfalls -->
<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
    <h3 style="color: #856404; margin-top: 0;">
        <span>⚠️</span> Common Staging Pitfalls to Avoid
    </h3>

    <div style="display: grid; gap: 12px;">
        <div style="display: flex; gap: 12px; background: white; padding: 12px; border-radius: 6px;">
            <span style="background: #ffc107; color: #856404; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">1</span>
            <div>
                <strong>Not confirming HPV status first</strong>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 0.9em;">The staging systems are completely different. Always check pathology.</p>
            </div>
        </div>

        <div style="display: flex; gap: 12px; background: white; padding: 12px; border-radius: 6px;">
            <span style="background: #ffc107; color: #856404; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">2</span>
            <div>
                <strong>Measuring nodes on long axis</strong>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 0.9em;">Always use SHORT axis. This is the standard for nodal measurements.</p>
            </div>
        </div>

        <div style="display: flex; gap: 12px; background: white; padding: 12px; border-radius: 6px;">
            <span style="background: #ffc107; color: #856404; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">3</span>
            <div>
                <strong>Overcalling carotid encasement</strong>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 0.9em;">Contact or abutment (≤270°) is NOT T4b. Must be &gt;270° circumferential.</p>
            </div>
        </div>

        <div style="display: flex; gap: 12px; background: white; padding: 12px; border-radius: 6px;">
            <span style="background: #ffc107; color: #856404; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">4</span>
            <div>
                <strong>Confusing intrinsic vs extrinsic tongue muscles</strong>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 0.9em;">Only EXTRINSIC = T4a (genioglossus, hyoglossus, styloglossus, palatoglossus).</p>
            </div>
        </div>

        <div style="display: flex; gap: 12px; background: white; padding: 12px; border-radius: 6px;">
            <span style="background: #ffc107; color: #856404; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">5</span>
            <div>
                <strong>Missing retropharyngeal nodes</strong>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 0.9em;">These count as regional nodes. Systematically check the retropharyngeal space.</p>
            </div>
        </div>

        <div style="display: flex; gap: 12px; background: white; padding: 12px; border-radius: 6px;">
            <span style="background: #ffc107; color: #856404; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0;">6</span>
            <div>
                <strong>Including edema in tumor measurement</strong>
                <p style="margin: 4px 0 0 0; color: #666; font-size: 0.9em;">Measure only the enhancing soft tissue component, not surrounding edema.</p>
            </div>
        </div>
    </div>
</div>

<!-- Imaging Tips -->
<div style="background: #e3f2fd; border: 1px solid #90caf9; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
    <h3 style="color: #1565c0; margin-top: 0;">
        <span>🔍</span> Key Imaging Tips
    </h3>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #1565c0;">
            <h4 style="margin: 0 0 8px 0; color: #1565c0;">Carotid Assessment</h4>
            <p style="margin: 0; color: #666; font-size: 0.9em;">
                &lt;180° = Contact<br>
                180-270° = Abutment<br>
                <strong>&gt;270° = Encasement (T4b)</strong>
            </p>
        </div>

        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #1565c0;">
            <h4 style="margin: 0 0 8px 0; color: #1565c0;">Node Measurement</h4>
            <p style="margin: 0; color: #666; font-size: 0.9em;">
                Always SHORT axis<br>
                Standard: &gt;1 cm<br>
                Level II: &gt;1.5 cm acceptable
            </p>
        </div>

        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #1565c0;">
            <h4 style="margin: 0 0 8px 0; color: #1565c0;">Skull Base Check</h4>
            <p style="margin: 0; color: #666; font-size: 0.9em;">
                Use bone windows:<br>
                Clivus, petrous apex,<br>
                pterygoid plates, foramina
            </p>
        </div>

        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #1565c0;">
            <h4 style="margin: 0 0 8px 0; color: #1565c0;">ENE Signs</h4>
            <p style="margin: 0; color: #666; font-size: 0.9em;">
                Irregular/spiculated margins<br>
                Fat infiltration<br>
                Matted nodes, IJ thrombosis
            </p>
        </div>
    </div>
</div>

<!-- Footer -->
<div style="background: #f8f9fa; border-radius: 8px; padding: 15px; text-align: center; color: #666;">
    <p style="margin: 0;">Based on <strong>AJCC 8th Edition</strong> Staging Manual for Oropharyngeal Squamous Cell Carcinoma</p>
    <p style="margin: 8px 0 0 0; font-size: 0.9em;">Always correlate with clinical findings and discuss complex cases at MDT</p>
</div>

</div>
"""

DIAGNOSIS = """Oropharyngeal Cancer - Algorithmic Approach to TNM Staging Scan Reporting

This comprehensive guide provides a systematic, step-by-step approach to staging oropharyngeal squamous cell carcinoma on CT/MRI. Use this algorithm when reporting staging scans to ensure accurate and consistent TNM staging.

Key Features:
• HPV-status driven staging (different systems for HPV+ vs HPV-)
• Mnemonics for T4b ("PACE") and T4a ("HELP-M")
• Size-based T staging reference table
• N staging comparison table (HPV+ vs HPV-)
• Common pitfalls to avoid
• Imaging tips for key structures

This case serves as a reference guide that can be linked to specific oropharyngeal cancer cases (base of tongue, tonsil, soft palate) for easy access during case review."""

QA_PAIRS = [
    {
        "question": "What is the most critical first step when staging oropharyngeal cancer?",
        "answer": "Check HPV/p16 status first. HPV-positive and HPV-negative oropharyngeal cancers use completely different staging systems. HPV+ has better prognosis and simpler N staging. If HPV status is unknown, stage as HPV-negative."
    },
    {
        "question": "What are the T4b (unresectable) features? Use a mnemonic.",
        "answer": "T4b = 'PACE'\n• Prevertebral fascia invasion\n• Artery (carotid encasement >270°)\n• Cranium (skull base invasion)\n• Extension (mediastinal)\n\nAny ONE of these features = T4b (unresectable disease)."
    },
    {
        "question": "What are the T4a features? Use a mnemonic.",
        "answer": "T4a = 'HELP-M'\n• Hard palate\n• Extrinsic tongue muscles (genioglossus, hyoglossus, styloglossus - NOT intrinsic!)\n• Larynx invasion\n• Pterygoid (medial muscle)\n• Mandible\n\nThese indicate advanced but potentially resectable disease."
    },
    {
        "question": "How do you measure lymph nodes for staging?",
        "answer": "Always measure the SHORT AXIS (perpendicular to the long axis). Standard threshold is >1 cm, though >1.5 cm is acceptable for level II nodes. Don't forget to check retropharyngeal nodes - they count as regional nodes for oropharyngeal cancer."
    },
    {
        "question": "How does ENE (extranodal extension) affect staging?",
        "answer": "ENE significantly affects staging ONLY in HPV-negative disease:\n• HPV-negative: Clinical ENE upgrades to N3a\n• HPV-positive: ENE does NOT change the imaging N stage\n\nSigns of ENE: irregular/spiculated margins, fat infiltration, matted nodes, IJ thrombosis."
    }
]


def create_algorithmic_case():
    """Create the oropharyngeal cancer algorithmic staging case."""
    with app.app_context():
        # Check if case already exists
        existing = Case.query.filter(
            Case.diagnosis.ilike('%algorithmic approach%oropharyngeal%')
        ).first()

        if existing:
            print(f"Case already exists: ID={existing.id}, {existing.case_number}")
            return existing

        # Create new case
        case = Case(
            case_number="HEAD-NECK-ALG-001",
            diagnosis=DIAGNOSIS,
            discussion=DISCUSSION_HTML,
            module=FRCRModule.CNS_HEAD_NECK,
            body_part=BodyPart.HEAD_NECK,
            age_group=AgeGroup.ADULT,
            status=CaseStatus.PUBLISHED,
            calculator_slug="oropharynx"  # Link to the oropharynx calculator
        )

        db.session.add(case)
        db.session.flush()  # Get the ID

        # Add Q&A pairs
        from models import Question, Answer
        for i, pair in enumerate(QA_PAIRS, start=1):
            question = Question(
                case_id=case.id,
                question_number=i,
                question_text=pair["question"]
            )
            answer = Answer(
                case_id=case.id,
                answer_number=i,
                answer_text=pair["answer"]
            )
            db.session.add(question)
            db.session.add(answer)

        db.session.commit()

        print(f"✅ Created algorithmic case:")
        print(f"   ID: {case.id}")
        print(f"   Case Number: {case.case_number}")
        print(f"   Calculator: {case.calculator_slug}")
        print(f"   Status: {case.status.value}")
        print(f"   Q&A Pairs: {len(QA_PAIRS)}")

        return case


if __name__ == "__main__":
    case = create_algorithmic_case()
    print(f"\nView case at: /view-case/{case.id}")
