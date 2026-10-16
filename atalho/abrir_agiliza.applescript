-- Abre o Agiliza-Zé pelo menu do DaVinci: Workspace > Workflow Integrations > Agiliza-Zé
tell application "DaVinci Resolve" to activate
delay 0.4
tell application "System Events"
	tell process "Resolve"
		click menu item "Agiliza-Zé" of menu "Workflow Integrations" of menu item "Workflow Integrations" of menu "Workspace" of menu bar 1
	end tell
end tell
