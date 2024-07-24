-- Services --
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Variables --
local remoteEvents = ReplicatedStorage:WaitForChild("Remote Events")
local remoteFunctions = ReplicatedStorage:WaitForChild("Remote Functions")

-- Events --
local countdownEvent = remoteEvents:WaitForChild("CountdownEvent")
local waitingEvent = remoteEvents:WaitForChild("WaitingEvent")
local winnerEvent = remoteEvents:WaitForChild("WinnerEvent")

-- Functions --
local function createOrGetGui(player)
	local gui = player:FindFirstChild("PlayerGui"):FindFirstChild("CountdownGui")
	
	if not gui then
		gui = Instance.new("ScreenGui", player:FindFirstChild("PlayerGui"))
		gui.Name = "CountdownGui"

		local textLabel = Instance.new("TextLabel", gui)
		textLabel.Size = UDim2.new(0.5, 0, 0.1, 0)
		textLabel.Position = UDim2.new(0.5, 0, 0, 20)
		textLabel.AnchorPoint = Vector2.new(0.5, 0)
		textLabel.Font = Enum.Font.SourceSansBold
		textLabel.TextScaled = true
		textLabel.BackgroundTransparency = 1
		textLabel.TextColor3 = Color3.new(1, 1, 1)
		textLabel.Name = "CountdownText"
	end
	
	return gui:FindFirstChild("CountdownText")
end

local function displayCountdown(timeLeft)
	local player = game.Players.LocalPlayer
	local textLabel = createOrGetGui(player)
	
	textLabel.Text = "Starting game in " .. timeLeft .. " seconds..."
	
	if timeLeft == 0 then
		wait(1)
		textLabel.Parent:Destroy()
	end
end

local runningAnimation = false

local function displayWaitingMessage()
	local player = game.Players.LocalPlayer
	local textLabel = createOrGetGui(player)
	
	local function animateEllipsis()
		runningAnimation = true
		local ellipsis = ""
		while runningAnimation do
			for i = 1, 3 do
				if not runningAnimation then break end
				ellipsis = string.rep(".", i)
				textLabel.Text = "Waiting for players" .. ellipsis
				wait(0.5)
			end
		end
	end
	
	if not runningAnimation then
		coroutine.wrap(animateEllipsis)()
	end
end

local function stopWaitingMessage()
	runningAnimation = false
end

local function displayWinnerMessage(winner)
	local player = game.Players.LocalPlayer
	local textLabel = createOrGetGui(player)

	textLabel.Text = "The winner is " .. winner .. "!"
	
	wait(5)
	
	textLabel.Parent:Destroy()
end

countdownEvent.OnClientEvent:Connect(displayCountdown)
waitingEvent.OnClientEvent:Connect(displayWaitingMessage)
winnerEvent.OnClientEvent:Connect(displayWinnerMessage)

-- Stop waiting animation when countdown starts
countdownEvent.OnClientEvent:Connect(stopWaitingMessage)