/**
 * PII Guard v2 — Detection Engine
 * Dual-layer protection: client-side (this file) + server-side (pii_guard.py)
 * Loaded globally via base.html. Thin fetch interceptor; all UI in pii-guard-ui.js.
 */
(function() {
    'use strict';

    // ======================== CONFIDENCE TIERS ========================
    var TIER_HIGH   = 'high';
    var TIER_MEDIUM = 'medium';
    var TIER_LOW    = 'low';

    // ======================== MEDICAL ALLOWLIST ========================
    var MEDICAL_ALLOWLIST = new Set([
        // Vertebral levels
        'C1','C2','C3','C4','C5','C6','C7',
        'T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12',
        'L1','L2','L3','L4','L5','S1','S2','S3','S4','S5',
        // Vertebral ranges
        'C1-C2','C2-C3','C3-C4','C4-C5','C5-C6','C6-C7',
        'T1-T2','T2-T3','T3-T4','T4-T5','T5-T6','T6-T7','T7-T8','T8-T9','T9-T10','T10-T11','T11-T12','T12-L1',
        'L1-L2','L2-L3','L3-L4','L4-L5','L5-S1',
        // TNM staging
        'T0','T1A','T1B','T1C','T2A','T2B','T2C','T3A','T3B','T4A','T4B',
        'N0','N1','N1A','N1B','N2','N2A','N2B','N3','N3A','N3B',
        'M0','M1','M1A','M1B','M1C',
        'STAGE I','STAGE IA','STAGE IB','STAGE II','STAGE IIA','STAGE IIB','STAGE IIC',
        'STAGE III','STAGE IIIA','STAGE IIIB','STAGE IIIC','STAGE IV','STAGE IVA','STAGE IVB',
        // Radiology / imaging
        'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
        'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
        'T1W','T2W','T1 WEIGHTED','T2 WEIGHTED','T1 W','T2 W',
        'DR','CR','US','XR',
        // Measurements
        'HU','SUV','ADC VALUE','SUV MAX','SUVMAX',
        // Contrast
        'IV CONTRAST',
        // Grading
        'G1','G2','G3','G4','GX',
        // RADS scoring
        'BI-RADS','BIRADS','PI-RADS','PIRADS','TI-RADS','TIRADS','LI-RADS','LIRADS',
        // Anatomy abbreviations
        'SA NODE','AV NODE','SI JOINT','SI JOINTS',
    ]);

    var IMAGING_MODALITY_TERMS = new Set([
        'CT','MRI','MRA','MRV','PET','SPECT','DEXA','BMD',
        'FLAIR','DWI','ADC','SWI','GRE','STIR','FIESTA','CISS',
        'XR','CXR','AXR','USS','HRCT','CECT','NCCT','MRE','MRCP',
    ]);

    var NER_FALSE_POSITIVE_TERMS = new Set([
        // Eponymous conditions / signs / procedures
        'GREY','BAKER','COLLES','CROHN','CUSHING','GRAVES','HASHIMOTO',
        'HODGKIN','WILMS','EWING','PAGET','DUPUYTREN','MECKEL','BARRETT',
        'BELL','ADDISON','MARFAN','PARKINSON','ALZHEIMER','RAYNAUD',
        'SJOGREN','WEGENER','BEHCET','HIRSCHSPRUNG','BUDD','CHIARI',
        'ARNOLD','DANDY','WALKER','KLATSKIN','WARTHIN','RICHTER',
        'VIRCHOW','TROUSSEAU','MURPHY','COURVOISIER','WHIPPLE',
        'HARTMANN','BILLROTH','NISSEN','BANKART','HILL','SACHS',
        'MOREL','LAVALLEE','MONTEGGIA','GALEAZZI','SMITH','BARTON',
        'CHAUFFEUR','BENNETT','ROLANDO','GAMEKEEPER','STENER','SEGOND',
        'PELLEGRINI','STIEDA','OSGOOD','SCHLATTER','SEVER','KOHLER',
        'FREIBERG','KIENBOCK','PREISER','LEGG','CALVE','PERTHES',
        'BLOUNT','SCHEUERMANN','CHANCE','JEFFERSON','HANGMAN',
        'SALTER','HARRIS','TILLAUX','MAISONNEUVE','LISFRANC','JONES',
        'MARCH','STRESS',
        // Radiology signs
        'FLEISCHNER','KERLEY','RIGLER','CHILAIDITI','WESTERMARK','FELSON',
        'HAMPTON','CODMAN','SUNBURST','ONION','TERRY','THOMAS',
        // Scoring / classification systems
        'BOSNIAK','FISHER','CHILD','PUGH','DEAUVILLE','NEER','MASON',
        'WEBER','SCHATZKER','GARDEN','GUSTILO','ANDERSON','ROCKWOOD',
        'DENIS','MAGERL','FRANKEL','ASIA','HUNT','HESS','SPETZLER',
        'MARTIN','LUGANO','ANN','ARBOR','CLARK','BRESLOW','GLEASON',
        'FUHRMAN','EDMONDSON','STEINER','CLAVIEN','DINDO','BISMUTH',
        'TODANI','HINCHEY','ALVARADO','BALTHAZAR','DUKE',
        // Anatomy / clinical
        'WHITE','WARD','LIVER','BRAIN','SPINE','BOWEL','COLON',
        'RECTUM','KIDNEY','LUNG','HEART','AORTA','PANCREAS',
        'SPLEEN','ADRENAL','BLADDER','PROSTATE','UTERUS','OVARY',
        'BREAST','THYROID','TRACHEA','OESOPHAGUS','ESOPHAGUS',
        // Report section headings
        'FINDINGS','IMPRESSION','INDICATION','TECHNIQUE','COMPARISON',
        'CLINICAL','HISTORY','CONCLUSION','RECOMMENDATION','COMMENT',
        'OPINION','SUMMARY','DISCUSSION','PROTOCOL','PROCEDURE',
        // Common radiology descriptors
        'NORMAL','UNREMARKABLE','STABLE','UNCHANGED','MILD','MODERATE',
        'SEVERE','ACUTE','CHRONIC','BILATERAL','LATERAL','MEDIAL',
        'ANTERIOR','POSTERIOR','SUPERIOR','INFERIOR','PROXIMAL','DISTAL',
    ]);

    function _isMedicalTerm(matchText) {
        if (!matchText) return false;
        var upper = matchText.trim().toUpperCase();
        if (MEDICAL_ALLOWLIST.has(upper)) return true;
        var parts = upper.split(/[-\/]/);
        if (parts.length >= 2 && parts.every(function(p) { return MEDICAL_ALLOWLIST.has(p.trim()); })) {
            return true;
        }
        return false;
    }

    // ======================== PII PATTERNS ========================

    var _NAME_STOP = "(?!(?:for|was|is|has|had|the|with|by|and|or|in|at|to|of|on|an|a"
        + "|this|that|no|who|will|may|should|could|would|not|been|being"
        + "|reviewed|presented|attended|referred|consulted|evaluated|diagnosed"
        + "|from|about|into|over|under|after|before|during|through"
        + "|name|report|study|scan|exam|history|findings|impression|clinical|imaging)\\b)";

    // Invalid NINO prefixes (Presidio-derived)
    var _NINO_INVALID = 'BG|GB|NK|KN|TN|NT|ZZ';

    var PII_PATTERNS = [
        // --- HIGH tier: always block ---
        {
            type: 'NHS Number', tier: TIER_HIGH,
            regex: /\bNHS\s*(?:no|number|#)?[:\s]+\d{3}[-\s]?\d{3}[-\s]?\d{4}\b/gi,
            description: 'NHS number detected'
        },
        {
            type: 'NHS Number', tier: TIER_HIGH,
            regex: /\bNHS\s*(?:no|number|#)?[:\s]+\d{6,10}\b/gi,
            description: 'NHS number detected (short format)'
        },
        {
            type: 'NHS Number', tier: TIER_HIGH,
            regex: /\b\d{3}[-\s]\d{3}[-\s]\d{4}\b/g,
            description: 'NHS number detected (format)',
            validate: _validateNHSChecksum
        },
        {
            type: 'US SSN', tier: TIER_HIGH,
            regex: /\b\d{3}-\d{2}-\d{4}\b/g,
            description: 'US Social Security Number detected'
        },
        {
            type: 'MRN / Hospital ID', tier: TIER_HIGH,
            regex: /\b(?:MRN|UHID|ACCN|ACC\s*NO|hospital\s*(?:id|no|number|#)|hosp\s*id|patient\s*(?:id|no)|medical\s*record)[:\s#]*\d{4,10}\b/gi,
            description: 'Medical Record Number detected'
        },
        {
            type: 'Email Address', tier: TIER_HIGH,
            regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
            description: 'Email address detected'
        },
        {
            type: 'UK National Insurance Number', tier: TIER_HIGH,
            regex: new RegExp('\\b(?!' + _NINO_INVALID + ')[A-Z]{2}\\d{6}[A-D]\\b', 'gi'),
            description: 'UK National Insurance Number detected'
        },
        {
            type: 'Aadhaar Number', tier: TIER_HIGH,
            regex: /\b\d{4}\s?\d{4}\s?\d{4}\b/g,
            description: 'Indian Aadhaar number detected'
        },
        {
            type: 'PAN Card', tier: TIER_HIGH,
            regex: /\b[A-Z]{5}\d{4}[A-Z]\b/g,
            description: 'Indian PAN card number detected'
        },
        {
            type: 'GMC Number', tier: TIER_HIGH,
            regex: /\b(?:GMC|gmc)\s*(?:no\.?|number|#|:)?\s*\d{7}\b/gi,
            description: 'UK GMC registration number detected'
        },
        {
            type: 'Possible Patient ID', tier: TIER_HIGH,
            regex: /^\d{7,10}$/gm,
            description: 'Bare number on own line — likely hospital number or patient ID'
        },

        // --- MEDIUM tier: warn ---
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: /\b(?:patient\s*name|patient|pt\s*name|pt|name)\s*[:=\-\s]\s*(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s*[A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))/gi,
            description: 'Possible patient name detected (with keyword + title)'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: new RegExp(
                "\\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\\b\\.?\\s*"
                + _NAME_STOP + "[A-Za-z][a-zA-Z'\\-]+"
                + "(?:\\s+" + _NAME_STOP + "[A-Za-z][a-zA-Z'\\-]+){0,3}"
                + "(?=\\s*(?:[,;.\\n|/()]|\\d|\\bage\\b|\\bgender\\b|\\bsex\\b|\\bdob\\b|\\bpresented\\b|\\battended\\b|\\bwas\\b|\\bis\\b|\\bhas\\b|\\bfor\\b|\\bwith\\b|\\breviewed\\b|\\breferred\\b|$))",
                "g"
            ),
            description: 'Patient name with title detected'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: /\b(?:patient\s*name|pt\s*name)\s*[:=\-\s]\s*[A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){0,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|$))/gi,
            description: 'Possible patient name detected'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: /\b[Nn]ame\s*[:=\-\s]\s*[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){1,3}(?=\s*(?:[,;.\n|]|\bage\b|\bgender\b|\bsex\b|\bdob\b|\baddress\b|\bmrn\b|\bnhs\b|\d|$))/g,
            description: 'Possible patient name detected (name keyword)'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: /\d{1,3}[-\s]?year[-\s]?old\b[^.\n]{0,30}?([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})(?=\s*(?:[,;.\n|]|\bpresented\b|\battended\b|\bwas\b|\bis\b|\bhas\b|\bwith\b|$))/g,
            description: 'Patient name after age context detected'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: new RegExp(
                "\\b[Pp](?:atient|t)(?:\\s*[:=\\-]\\s*|\\s+)"
                + _NAME_STOP + "([A-Z][a-zA-Z'\\-]+"
                + "(?:\\s+" + _NAME_STOP + "[A-Z][a-zA-Z'\\-]+){0,3})"
                + "(?=\\s*(?:[,;.\\n|/()]|\\d|\\bpresented\\b|\\battended\\b|\\bwas\\b|\\bis\\b|\\bhas\\b|\\bwith\\b|\\bfor\\b|$))",
                "g"
            ),
            description: 'Patient name after keyword detected'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: new RegExp(
                "\\b[Pp](?:atient|t)\\s+(?:name|full\\s*name)\\s*[:=\\-]?\\s*"
                + _NAME_STOP + "([A-Z][a-zA-Z'\\-]+"
                + "(?:\\s+" + _NAME_STOP + "[A-Z][a-zA-Z'\\-]+){0,3})"
                + "(?=\\s*(?:[,;.\\n|/()]|\\d|\\bage\\b|\\bgender\\b|\\bsex\\b|\\bdob\\b|\\bpresented\\b|\\battended\\b|\\bwas\\b|\\bis\\b|\\bhas\\b|\\bwith\\b|\\bfor\\b|$))",
                "g"
            ),
            description: 'Patient name after "patient name" keyword'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: new RegExp(
                "\\b[Tt]his\\s+is\\s+"
                + _NAME_STOP + "[A-Z][a-zA-Z'\\-]{2,}"
                + "(?:\\s+" + _NAME_STOP + "[A-Z][a-zA-Z'\\-]+){1,3}"
                + "(?=\\s*,?\\s+(?:a\\s+|an\\s+)?\\d{1,3}[\\-\\s]?years?[\\-\\s]?old\\b)",
                "g"
            ),
            description: 'Patient name after introduction detected'
        },
        {
            type: 'Patient Name', tier: TIER_MEDIUM,
            regex: /\b[A-Z]\.?\s+[A-Z][a-zA-Z'-]{2,}(?:\s+[A-Z][a-zA-Z'-]+)?(?=\s*(?:,\s*\d|\s+age\b|\s+\d{1,3}\s*(?:year|yr|yo|y\.?o)\b|\s+(?:male|female|M|F)\b))/g,
            description: 'Probable patient name (initial + surname near age/gender context)'
        },
        {
            type: 'Doctor / Clinician Name', tier: TIER_MEDIUM,
            regex: /\b(?:referred\s+by|reporting\s+(?:radiologist|doctor|consultant)|reported\s+by|consultant|registrar|SpR|SHO|GP)\b\s*[:=\-]?\s*(?:Dr\.?\s+)?[A-Z][a-zA-Z'-]+(?:\s+[A-Z]\.?[a-zA-Z'-]*){0,3}/gi,
            description: 'Referring/reporting clinician name detected'
        },
        {
            type: 'Doctor / Clinician Name', tier: TIER_MEDIUM,
            regex: /\bDr\.?\s+[A-Z][a-zA-Z'-]+(?:\s+[A-Z]\.?[a-zA-Z'-]*){1,3}\b/g,
            description: 'Doctor name detected'
        },
        {
            type: 'Date of Birth', tier: TIER_MEDIUM,
            regex: /\b(?:DOB|dob|D\.O\.B|born|date\s*of\s*birth|birth\s*date)[:\s]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b/gi,
            description: 'Date of birth detected'
        },
        {
            type: 'Phone Number', tier: TIER_MEDIUM,
            regex: /\b(?:phone|tel|mobile|cell|contact|ph)\s*[:=\-#]?\s*\+?[(\d][\d\s\-.()]{7,15}\d/gi,
            description: 'Phone number detected'
        },
        {
            type: 'Phone Number', tier: TIER_MEDIUM,
            regex: /\b(?:his|her|my|their|the)\s+(?:number|no|contact)\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b/gi,
            description: 'Phone number detected (context)'
        },
        {
            type: 'Phone Number', tier: TIER_MEDIUM,
            regex: /\bnumber\s+(?:is|was)\s*:?\s*\+?[\d][\d\s\-.()]{6,15}\d\b/gi,
            description: 'Phone number detected (keyword)'
        },
        {
            type: 'Patient Address', tier: TIER_MEDIUM,
            regex: /\b(?:address|addr|home)\s*[:=\-]\s*[A-Za-z0-9][A-Za-z0-9\s,.''-]{5,}/gi,
            description: 'Patient address detected'
        },

        // --- LOW tier: soft-warn ---
        {
            type: 'UK Postcode', tier: TIER_LOW,
            regex: /\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b/gi,
            description: 'UK postcode detected'
        },
        {
            type: 'Phone Number', tier: TIER_LOW,
            regex: /\+\d{1,3}[\s.-]?\d{4,5}[\s.-]?\d{4,6}\b/g,
            description: 'International phone number detected'
        },
        {
            type: 'Patient Age', tier: TIER_LOW,
            regex: /\b(?:age|aged)\s*[:=\-]\s*\d{1,3}\b/gi,
            description: 'Patient age detected'
        },
        {
            type: 'Patient Gender', tier: TIER_LOW,
            regex: /\b(?:gender|sex)\s*[:=\-]\s*(?:male|female|m|f|other|non-binary)\b/gi,
            description: 'Patient gender detected'
        },
        {
            type: 'IP Address', tier: TIER_LOW,
            regex: /\b(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\b/g,
            description: 'IP address detected (HIPAA identifier)'
        },
    ];

    // NHS MOD-11 checksum validator (OpenRedaction-derived)
    function _validateNHSChecksum(matchText) {
        var digits = matchText.replace(/[\s-]/g, '');
        if (digits.length !== 10) return true; // can't validate, allow through
        var weights = [6, 2, 7, 1, 3, 6, 2, 7, 1, 3];
        var sum = 0;
        for (var i = 0; i < 10; i++) {
            sum += parseInt(digits[i], 10) * weights[i];
        }
        return sum % 11 === 0;
    }

    // ======================== SCANNER ========================

    function scan(text) {
        if (!text || typeof text !== 'string' || text.length < 5) {
            return { hasPII: false, matches: [] };
        }

        var matches = [];
        for (var p = 0; p < PII_PATTERNS.length; p++) {
            var pattern = PII_PATTERNS[p];
            pattern.regex.lastIndex = 0;
            var match;
            while ((match = pattern.regex.exec(text)) !== null) {
                var m = {
                    type: pattern.type,
                    match: match[0],
                    index: match.index,
                    length: match[0].length,
                    tier: pattern.tier,
                    description: pattern.description
                };
                // Run optional validator (e.g. NHS checksum)
                if (pattern.validate && !pattern.validate(match[0])) continue;
                matches.push(m);
            }
        }

        // 3-stage false-positive suppression
        // Stage 1: Medical allowlist
        var filtered = matches.filter(function(m) { return !_isMedicalTerm(m.match); });

        // Stage 2: Imaging modality filter for name matches
        filtered = filtered.filter(function(m) {
            if (m.type === 'Patient Name' || m.type === 'Doctor / Clinician Name') {
                var words = m.match.split(/[\s:=\-]+/);
                for (var i = 0; i < words.length; i++) {
                    if (words[i] && IMAGING_MODALITY_TERMS.has(words[i].toUpperCase())) return false;
                }
            }
            return true;
        });

        // Stage 3: Eponym filter — skip names where ALL content words are medical eponyms
        filtered = filtered.filter(function(m) {
            if (m.type === 'Patient Name' || m.type === 'Doctor / Clinician Name') {
                var nameWords = m.match.split(/[\s:=.\-]+/).filter(function(w) {
                    return w.length > 0 && !/^(pt|patient|name|dr|mr|mrs|ms|miss|prof)$/i.test(w);
                });
                if (nameWords.length > 0 && nameWords.every(function(w) {
                    return NER_FALSE_POSITIVE_TERMS.has(w.toUpperCase());
                })) return false;
            }
            return true;
        });

        return { hasPII: filtered.length > 0, matches: filtered };
    }

    function _dedupeMatches(matches) {
        var seen = new Set();
        var unique = [];
        for (var i = 0; i < matches.length; i++) {
            var key = matches[i].match;
            if (key && !seen.has(key)) {
                seen.add(key);
                unique.push(matches[i]);
            }
        }
        unique.sort(function(a, b) { return b.match.length - a.match.length; });
        return unique;
    }

    function redact(text, matches) {
        if (!matches || matches.length === 0) return text;
        var unique = _dedupeMatches(matches);
        var result = text;
        for (var i = 0; i < unique.length; i++) {
            var matchText = unique[i].match;
            if (matchText && result.indexOf(matchText) !== -1) {
                result = result.split(matchText).join('[REDACTED]');
            }
        }
        return result;
    }

    function remove(text, matches) {
        if (!matches || matches.length === 0) return text;
        var unique = _dedupeMatches(matches);
        var result = text;
        for (var i = 0; i < unique.length; i++) {
            var matchText = unique[i].match;
            if (matchText && result.indexOf(matchText) !== -1) {
                result = result.split(matchText).join('');
            }
        }
        return result.replace(/  +/g, ' ').trim();
    }

    // ======================== DISMISS TRACKING ========================

    var _dismissedKeys = new Set();

    function _dismissKey(match) {
        return match.type + ':' + match.match;
    }

    function dismiss(match) {
        _dismissedKeys.add(_dismissKey(match));
    }

    function isDismissed(match) {
        return _dismissedKeys.has(_dismissKey(match));
    }

    function filterDismissed(matches) {
        return matches.filter(function(m) { return !_dismissedKeys.has(_dismissKey(m)); });
    }

    function clearDismissals() {
        _dismissedKeys.clear();
    }

    // ======================== FETCH INTERCEPTOR ========================
    // Thin pass-through: only adds X-PII-Override header when _overrideActive flag is set.

    var _overrideActive = false;

    function setOverride(val) { _overrideActive = !!val; }
    function getOverride() { return _overrideActive; }

    function attachToFetch() {
        var originalFetch = window.fetch;

        window.fetch = function(url, options) {
            if (!options || !options.body) return originalFetch.call(this, url, options);
            if (!options.method || ['POST', 'PUT'].indexOf(options.method.toUpperCase()) === -1) {
                return originalFetch.call(this, url, options);
            }

            // Add override header if flag is set
            if (_overrideActive) {
                _overrideActive = false;
                if (!options.headers) options.headers = {};
                if (options.headers instanceof Headers) {
                    options.headers.set('X-PII-Override', '1');
                } else {
                    options.headers['X-PII-Override'] = '1';
                }
            }

            return originalFetch.call(this, url, options);
        };
    }

    // ======================== PUBLIC API ========================

    window.PIIGuard = {
        scan: scan,
        redact: redact,
        remove: remove,
        attachToFetch: attachToFetch,
        setOverride: setOverride,
        getOverride: getOverride,
        dismiss: dismiss,
        isDismissed: isDismissed,
        filterDismissed: filterDismissed,
        clearDismissals: clearDismissals,
        isMedicalTerm: _isMedicalTerm,
        PII_PATTERNS: PII_PATTERNS,
        MEDICAL_ALLOWLIST: MEDICAL_ALLOWLIST,
        IMAGING_MODALITY_TERMS: IMAGING_MODALITY_TERMS,
        NER_FALSE_POSITIVE_TERMS: NER_FALSE_POSITIVE_TERMS,
        TIER_HIGH: TIER_HIGH,
        TIER_MEDIUM: TIER_MEDIUM,
        TIER_LOW: TIER_LOW,
        // protect() is defined by pii-guard-ui.js and injected onto this namespace
    };

})();
