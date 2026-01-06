-- AppleScript to open FRCR Examiner and handle Gatekeeper
-- This script removes quarantine and opens the app

on run
    set appPath to "/Applications/FRCR Examiner.app"
    
    try
        -- Remove quarantine attribute
        do shell script "xattr -rd com.apple.quarantine " & quoted form of appPath with administrator privileges
        
        -- Open the app
        tell application "Finder"
            open appPath
        end tell
        
        display dialog "FRCR Examiner is now opening. The app has been trusted and will open normally in the future." buttons {"OK"} default button "OK" with icon note
    on error errMsg
        display dialog "Error: " & errMsg & return & return & "Please try right-clicking the app and selecting 'Open' instead." buttons {"OK"} default button "OK" with icon stop
    end try
end run

