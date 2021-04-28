extensions [ nw ]

breed [nodes node]
breed [cars car]


globals
[
  grid-x-inc               ;; the amount of patches in between two roads in the x direction
  grid-y-inc               ;; the amount of patches in between two roads in the y direction
  acceleration             ;; the constant that controls how much a car speeds up or slows down by if
                           ;; it is to accelerate or decelerate

  speed-limit   ;; the maximum speed of the cars
  phase                    ;; keeps track of the phase
  num-cars-stopped         ;; the number of cars that are stopped during a single pass thru the go procedure
  city-income              ;; money the city currently makes
  city-loss                ;; money the city loses because people do not buy tickets
  total-fines              ;; sum of all fines collected by the city
  num-lots                 ;; number of lots
  num-spaces               ;; number of individual spaces
  cars-to-create           ;;number of cars that have to be created to replace those leaving the map
  mean-income              ;; mean income of turtles
  median-income            ;;median-income of turtles
  color-counter            ;;counter to ensure that every group of lots is visited only twice

  selected-car   ;; the currently selected car //inserted

  ;; patch agentsets
  intersections ;; agentset containing the patches that are intersections
  roads         ;; agentset containing the patches that are roads
  yellow-lot    ;; agentset containing the patches that contain the spaces for the yellow lot
  green-lot     ;; agentset containing the patches that contain the spaces for the green lot
  orange-lot    ;; agentset containing the patches that contain the spaces for the orange lot
  blue-lot      ;; agentset containing the patches that contain the spaces for the blue lot
  lots          ;; agentset containing all patches that are parking slots
  finalpatches  ;;agentset containing all patches that are at the end of streets
  initial-spawnpatches ;;agentset containing all patches for initial spawning
  spawnpatches   ;;agentset containing all patches that arebeginning of streets
]

nodes-own
[

]
cars-own
[
  ;;speed     ;; the speed of the turtle
  ;;up-car?   ;; true if the turtle moves downwards and false if it moves to the right
  wait-time ;; the amount of time since the last time a turtle has moved

  speed         ;; the current speed of the car
  park-time     ;; the time the driver wants to stay in the parking-spot
  park          ;; the driver's probability to be searching for a parking space
  paid?         ;; true if the car paid for its spot
  looksforparking? ;;while underway the driver does not look for parking. In the street with the parking place it gets enabled
  parked?       ;; true if the car is parked
  hasparked?    ;; false until the car parks the first time.
  just-parked-countdown  ;; countdown (-> cars should not repark immediately)
  time-parked     ;; time to park
  income          ;; income of actor
  wtp             ;; Willigness to Pay for Parking
  continue-search? ;;changes direction and searches other parking spaces
  parking-offender? ;;boolean for parking offenders
  lots-checked     ;;lots checked by the driver
  skip-intersection? ;;  true if intersection should be skipped to reach other parking-lots
  direction-turtle ;;turtle dircetion
  nav-goal
  nav-prklist      ;list of parking spots sorted by distance to nav-goal
  nav-hastarget?
  nav-pathtofollow
  income-grade
  search-time    ;;time to find a parking space
  reinitialize? ;;for agents who have left the map
  fee-income-share ;;fee as a portion of income

]

patches-own
[
  road?           ;; true if the patch is a road
  horizontal?     ;; true for road patches that are horizonatal; false for vertical roads
                  ;;-1 for non-road patches
  alternate-direction? ;; true for every other parallel road.
                       ;;-1 for non-road patches
  direction       ;; one of "up", "down", "left" or "right"
                  ;;-1 for non-road patches
  intersection?   ;; true if the patch is at the intersection of two roads
  dirx
  diry
  green-light-up? ;; true if the green light is above the intersection.  otherwise, false.
                  ;; false for a non-intersection patches.
  my-row          ;; the row of the intersection counting from the upper left corner of the
                  ;; world.  -1 for non-intersection and non-horizontal road patches.
  my-column       ;; the column of the intersection counting from the upper left corner of the
                  ;; world.  -1 for non-intersection and non-vertical road patches.
  my-phase        ;; the phase for the intersection.  -1 for non-intersection patches.
  auto?           ;; whether or not this intersection will switch automatically.
                  ;; false for non-intersection patches.
  car?            ;; whether there is a car on this patch
  fee             ;; price of parking here
  lot-id          ;; id of lot
  center-distance ;;distance to center of map
]


;;;;;;;;;;;;;;;;;;;;;;
;; Setup Procedures ;;
;;;;;;;;;;;;;;;;;;;;;;

;; Initialize the display by giving the global and patch variables initial values.
;; Create num-cars of turtles if there are enough road patches for one turtle to
;; be created per road patch. Set up the plots.
to setup
  clear-all
  setup-globals
  set speed-limit 0.3

  ;; First we ask the patches to draw themselves and set up a few variables
  setup-patches

  set-default-shape cars "car"

  if (num-cars > count roads)
  [
    user-message (word "There are too many cars for the amount of "
      "road.  Either increase the amount of roads "
      "by increasing the GRID-SIZE-X or "
      "GRID-SIZE-Y sliders, or decrease the "
      "number of cars by lowering the NUMBER slider.\n"
      "The setup has stopped.")
    stop
  ]

  ;; Now create the turtles and have each created turtle call the functions setup-cars and set-car-color
  create-cars num-cars
  [
    setup-cars
    set-car-color
    record-data
    ifelse park >= 25 [
      if random 100 >= 50 [
        setup-parked
        set reinitialize? true
      ]
    ]
    [
      set nav-prklist []
      set reinitialize? true
    ]
  ]

  ;; give the turtles an initial speed
  ask cars [ set-car-speed ]

  if demo-mode [
    let example_car one-of cars with [park > 25 and parked? = false ]
    ask example_car [set color cyan]
    watch example_car
    inspect example_car
    ask [nav-goal] of example_car [set pcolor cyan]
  ]
  reset-ticks
end

to setup-finalroads
  set finalpatches roads with [(pxcor = max-pxcor and direction = "right") or (pxcor = min-pxcor and direction = "left") or (pycor  = max-pycor and direction = "up") or (pycor = min-pycor and direction = "down") ]
  ;ask finalpatches [set pcolor yello]
  ;show finalpatches
end
to setup-spawnroads
  set spawnpatches roads with [(pxcor = max-pxcor and direction = "left") or (pxcor = min-pxcor and direction = "right") or (pycor  = max-pycor and direction = "down") or (pycor = min-pycor and direction = "up") ]
  ;show finalpatches
end

to setup-initial-spawnroads
  set initial-spawnpatches roads with [(pxcor > min-pxcor / 2  and direction = "left") or (pxcor < max-pxcor / 2 and direction = "right") or (pycor > min-pycor / 2 and direction = "down") or (pycor < max-pycor / 2 and direction = "up") ]
end



;; Initialize the global variables to appropriate values
to setup-globals
  set phase 0
  set num-cars-stopped 0
  set grid-x-inc 15
  set grid-y-inc floor(grid-x-inc * 1.2) ;; x*1,43 is the Relation of the Mannheim quadrate but 1.2 looks nicer

  ;; don't make acceleration 0.1 since we could get a rounding error and end up on a patch boundary
  set acceleration 0.099
end

;; Make the patches have appropriate colors, set up the roads and intersections agentsets,
;; and initialize the traffic lights to one setting
to setup-patches
  ;; initialize the patch-owned variables and color the patches to a base-color
  ask patches
  [
    set road? false
    set horizontal? -1
    set alternate-direction? -1
    set direction -1
    set intersection? false
    set auto? false
    set green-light-up? true
    set my-row -1
    set my-column -1
    set my-phase -1
    set pcolor brown + 3
    set center-distance [distancexy 0 0] of self
    ;; coloring for better counting
    ;if (pycor mod 2 = 1 and pxcor mod 2 = 1) [set pcolor brown]
  ]

  ;; initialize the global variables that hold patch agentsets

  set roads patches with
    [(floor((pxcor + max-pxcor - floor(grid-x-inc - 1)) mod grid-x-inc) = 8) or
      (floor((pycor + max-pycor) mod grid-y-inc) = 8)]
  setup-roads
  set intersections roads with
    [(floor((pxcor + max-pxcor - floor(grid-x-inc - 1)) mod grid-x-inc) = 8) and
      (floor((pycor + max-pycor) mod grid-y-inc) = 8)]

  setup-intersections
  setup-lots
  setup-finalroads
  setup-spawnroads
  setup-initial-spawnroads
  setup-nodes
end

to setup-roads
  ask roads [
    set road? true
    set pcolor white
    ;; check if patches left and right (x +-1 road?) are patches if yes, then it is a horizontal road
    ifelse (floor((pxcor + max-pxcor - floor(grid-x-inc - 1)) mod grid-x-inc) = 8)
    [set horizontal? false];; vertical road
    [set horizontal? true];; horizontal road

    ifelse horizontal?
    [ ;; horizontal roads get the row set
      set my-row floor((pycor + max-pycor) / grid-y-inc)
      ifelse my-row mod 2 = 1 ;; every other horizontal road has an alternate direction: normal + horizontal = right
      [ set alternate-direction? false
        set dirx "right"]
      [ set alternate-direction? true
        set dirx "left"]
      set direction dirx
    ]
    [ ;; vertial roads get the row set
      set my-column floor((pxcor + max-pxcor) / grid-x-inc)
      ifelse my-column mod 2 = 1 ;; every other vertial road has an alternate direction: normal + vertical = down
      [ set alternate-direction? true
        set diry "up"]
      [ set alternate-direction? false
        set diry "down"]
      set direction diry
    ]


    sprout-nodes 1 [
      set size 0.2
      set shape "circle"
      set color white
    ]


  ]
end

to setup-nodes
  ask nodes [
    if not member? patch-here finalpatches [
      (ifelse
        dirx = "left" [create-links-to nodes-on patch-at -1 0[set hidden? hide-nodes]]
        dirx = "right" [create-links-to nodes-on patch-at 1 0[set hidden? hide-nodes] ])

      (ifelse
        diry = "up" [create-links-to nodes-on patch-at 0 1[set hidden? hide-nodes]]
        diry = "down" [create-links-to nodes-on patch-at 0 -1[set hidden? hide-nodes] ])
    ]
  ]
end


;; Give the intersections appropriate values for the intersection?, my-row, and my-column
;; patch variables.  Make all the traffic lights start off so that the lights are red
;; horizontally and green vertically.
to setup-intersections
  ask intersections
  [
    set intersection? true
    set green-light-up? true
    set my-phase 0
    set auto? true
    set my-row floor((pycor + max-pycor) / grid-y-inc)
    ifelse my-row mod 2 = 1 ;; every other horizontal road has an alternate direction: normal + horizontal = right
      [ set dirx "right"]
    [ set dirx "left"]
    set my-column floor((pxcor + max-pxcor) / grid-x-inc)
    ifelse my-column mod 2 = 1 ;; every other vertial road has an alternate direction: normal + vertical = down
      [ set diry "up"]
    [ set diry "down"]
    set-signal-colors
  ]
end

to setup-lots;;intialize dynamic lots
  set num-lots 1
  let max-x max [pxcor] of intersections
  let min-x min [pxcor] of intersections
  let max-y max [pycor] of intersections
  let min-y min [pycor] of intersections
  ask intersections [
    let x [pxcor] of self
    let y [pycor] of self
    if x != max-x and x != min-x and y != max-y and y != min-y [ ;;lots at the beginning and end of grid do not work with navigation
      if random 100 <= lot-distribution-percentage / 2 [
        let potential-lots patches with [((pxcor = x + 1 ) or (pxcor = x - 1)) and (((pycor <= y + ( grid-y-inc * .75)) and (pycor >= y + (grid-y-inc * .25))) or ((pycor >= y - ( grid-y-inc * .75)) and (pycor <= y - (grid-y-inc * .25))))]
        let average-distance mean [center-distance] of potential-lots
        ask potential-lots [
          set center-distance average-distance
          set lot-id num-lots
        ]
        set num-lots num-lots + 1
      ]
      if random 100 <= lot-distribution-percentage / 2  [
        let potential-lots patches with [((pycor = y + 1 ) or (pycor = y - 1)) and (((pxcor <= x + ( grid-x-inc * .75)) and (pxcor >= x + (grid-x-inc * .25))) or ((pxcor >= x - ( grid-x-inc * .75)) and (pxcor <= x - (grid-x-inc * .25))))]
        let average-distance mean [center-distance] of potential-lots
        ask potential-lots[
          set center-distance average-distance
          set lot-id num-lots
        ]
        set num-lots num-lots + 1
      ]
    ]
  ]
  let max-distance max [center-distance] of patches  with [lot-id != 0]
  set yellow-lot patches with [lot-id != 0 and center-distance <= max-distance * 0.4]
  set orange-lot patches with [lot-id != 0 and center-distance <= max-distance * 0.6 and center-distance > max-distance * 0.4]
  set green-lot patches with [lot-id != 0 and center-distance <= max-distance * 0.8 and center-distance > max-distance * 0.6]
  set blue-lot patches with  [lot-id != 0 and center-distance <= max-distance and center-distance > max-distance * 0.8]
  set lots (patch-set yellow-lot green-lot orange-lot blue-lot)
  set num-spaces count lots


  ask yellow-lot [
    set pcolor yellow
    set fee yellow-lot-fee
  ]
  ask green-lot [
    set pcolor green
    set fee green-lot-fee
  ]
  ask orange-lot [
    set pcolor orange
    set fee orange-lot-fee
  ]
  ask blue-lot [
    set pcolor blue - 10
    set fee blue-lot-fee
  ]
End

;; Initialize the turtle variables to appropriate values and place the turtle on an empty road patch.
to setup-cars  ;; turtle procedure
  set speed 0
  set wait-time 0
  ifelse reinitialize? = 0 [
    put-on-empty-road
    set income draw-income
  ]
  [
    move-to one-of spawnpatches with [not any? cars-on self]
    set income draw-sampled-income
  ]

  set direction-turtle [direction] of patch-here
  set hasparked? false
  set looksforparking? false
  if intersection?
  [
    ifelse random 2 = 0
    [ set direction-turtle [dirx] of patch-here ]
    [ set direction-turtle [diry] of patch-here ]
  ]


  ;;
  set heading (ifelse-value
    direction-turtle = "up" [ 0 ]
    direction-turtle = "down"[ 180 ]
    direction-turtle = "left" [ 270 ]
    direction-turtle = "right"[ 90 ])

  set-navgoal
  ;;set nav-goal one-of patches with [pcolor = brown + 3]
  set nav-prklist besmartie patch-here nav-goal
  set nav-hastarget? false


  set park random 100
  set park-time 300 + random 3000
  set parked? false
  set reinitialize? false
  set wtp income / 12 * wtp-income-share
  set income-grade find-income-grade

  set continue-search? false ;;default change required
  set skip-intersection? false
  set parking-offender? one-of [true false]
  set lots-checked no-patches
end

to setup-parked
  set parked? true
  set hasparked? true
  set looksforparking? false
  set nav-prklist []
  set nav-hastarget? false
  let inital-lot one-of lots with [not any? turtles-on self]
  move-to inital-lot
  ask inital-lot [set car? true]
  let parking-fee ([fee] of inital-lot * (park-time / 600))  ;; 100 ticks equal one hour
  set fee-income-share (parking-fee / (income / 12))
  ifelse (wtp >= parking-fee)
  [
    set paid? true
  ]
  [
    set paid? false
  ]
  set-car-color
  (foreach [0 0 1 -1] [-1 1 0 0] [[a b]->
    if ((member? patch-at a b roads))[
      set direction-turtle [direction] of patch-at a b
      set heading (ifelse-value
        direction-turtle = "up" [ 0 ]
        direction-turtle = "down"[ 180 ]
        direction-turtle = "left" [ 270 ]
        direction-turtle = "right"[ 90 ])
      stop
    ]
    ]
  )
end

;; Find a road patch without any turtles on it and place the turtle there.
to put-on-empty-road  ;; turtle procedure
  move-to one-of initial-spawnpatches with [not any? cars-on self]
end

to-report besmartie [current goal]
  let templots lots
  let favparkplätze []

  while [count templots > 0] [
    ;ask goal [ show min-one-of templots [distance myself] ]
    let i min-one-of templots [distance goal]
    set favparkplätze insert-item 0 favparkplätze [lot-id] of i
    set templots templots with [lot-id != [lot-id] of i]
    ;set templots remove patches with [pcolor = [pcolor] of i] templots
    set color-counter color-counter + 1
    if color-counter = 1[
      set templots templots with [pcolor != [pcolor] of i]
      set color-counter 0
    ]
  ]
  set favparkplätze reverse favparkplätze
  set color-counter 0
  report favparkplätze
end

to set-navgoal
  let potential-goals patches with [pcolor = brown + 3]
  let max-distance max [center-distance] of potential-goals
  let switch random 10
  (ifelse
    switch <= 3 [
      set nav-goal one-of potential-goals with [center-distance <= max-distance * 0.25]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance * 0.25][
          set pcolor cyan
        ]
      ]
    ]
    switch > 3 and switch <= 6 [
      set nav-goal one-of potential-goals with [center-distance <= max-distance * 0.4 and center-distance > max-distance * 0.25]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance * 0.4 and center-distance > max-distance * 0.25][
          set pcolor pink
        ]
      ]
    ]
    switch > 6 and switch <= 8 [
      set nav-goal one-of potential-goals with [center-distance <= max-distance * 0.55 and center-distance > max-distance * 0.4]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance * 0.55 and center-distance > max-distance * 0.4][
          set pcolor violet
        ]
      ]
    ]
    switch = 9[
      set nav-goal one-of potential-goals with [center-distance <= max-distance and center-distance > max-distance * 0.55]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance and center-distance > max-distance * 0.55][
          set pcolor turquoise
        ]
      ]
  ])
end

;;;;;;;;;;;;;;;;;;;;;;;;
;; Runtime Procedures ;;
;;;;;;;;;;;;;;;;;;;;;;;;

;; Run the simulation
to go

  ;; have the intersections change their color
  set-signals
  set num-cars-stopped 0

  ;; set the turtles speed for this time thru the procedure, move them forward their speed,
  ;; record data for plotting, and set the color of the turtles to an appropriate color
  ;; based on their speed
  ask cars
  [
    if patch-ahead 1 = nobody [ ;;debugging
      set cars-to-create cars-to-create +  1
      die
    ]
    if (member? patch-ahead 1 finalpatches) and (reinitialize? = true) [
      move-to patch-ahead 1
      set cars-to-create cars-to-create +  1
      die
    ]

    ifelse parked? != true
    [
      ;if hat keinen pfad gespeicher
      if not nav-hastarget?[
        ;; if I have already parked, I can delete my parking list.

        ifelse not empty? nav-prklist
        ;setze neuen Pfad mit der obersten Ding in nav-prklist
        [set nav-pathtofollow determine-path one-of nodes-on patch-here first nav-prklist]
        ;;If the parking list is empty either all parkingspots were tried or the car has already parked
        [ set nav-pathtofollow determine-finaldestination one-of nodes-on patch-here]

        set nav-hastarget? true
      ]

      ;==================================================
      ifelse not empty? nav-pathtofollow [
        let nodex first nav-pathtofollow
        set-car-speed
        face nodex ;evtl abändern
        fd speed
        if intersection? and not any? cars-on patch-ahead 1 [
          ;in case someoned looked for a parking lot, after reaching the end of a street (=Intersection) he does not look anymore
          set looksforparking? false
          move-to nodex
        ]
        ;wenn wir node erreicht haben,
        if one-of nodes-here = nodex [
          ;lösche 1. node aus nav-pathtofollow
          set nav-pathtofollow remove-item 0 nav-pathtofollow
        ]
        ;show nav-pathtofollow
      ]
      ;ifelse is empty
      [
        ;soll parkplats suchen
        set looksforparking? true
        ;soll nav- has target false machen
        set nav-hastarget? false
        ;soll erstes item aus nav-prklist löschen
        if not empty? nav-prklist [ ;;Dummy implementation
          set nav-prklist remove-item 0 nav-prklist
        ]

      ]
      ;==================================================
      if park >= 25 and looksforparking?
      ;if looksforparking?
      [
        park-car
      ]
      record-data
      set-car-color
      decrease-parked-countdown
      ;;check-park-prob
    ]
    [
      unpark-car
    ]
    update-search-time ;;increments search-time if not parked
  ]

  ;; update the phase and the global clock
  control-lots
  update-fees
  recreate-cars


  next-phase
  tick
end

;;;;;;;;;;;;;;;;
;; Navigation ;;
;;;;;;;;;;;;;;;;

to-report determine-finaldestination [start-node]
  let finalnodes nodes-on finalpatches
  let finalnode min-one-of finalnodes [length(nw:turtles-on-path-to one-of nodes-here)]
  ; ask one-of nodes-here [let path nw:turtles-on-path-to finalnode]
  ; set nav-pathtofollow path
  let path 0
  ask start-node [set path nw:turtles-on-path-to finalnode]
  report path
end


to-report determine-path [start lotID ]
  let lotproxy one-of lots with [lot-id = lotID]
  let node-proxy 0
  ask lotproxy [
    set node-proxy one-of nodes-on neighbors4
    ;show node-proxy
    ;ask one-of lots with [pcolor = lotID]

  ]

  let previous node-proxy
  ask node-proxy[
    ;show one-of in-link-neighbors
    ;Show "start"
    let current one-of in-link-neighbors
    ;show "Current:"
    ;show current
    let next 0
    let indegree 1
    while [indegree = 1]
    [

      set previous current
      ask current [
        set next one-of in-link-neighbors
      ]
      set current next
      ask current [
        set indegree count in-link-neighbors
      ]
    ]
  ]
  let path 0
  ask start [set path nw:turtles-on-path-to previous]

  report path
end

to change-direction

  (ifelse direction-turtle = "up" and dirx = "left"
    [
      set heading 270
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "left"
        set continue-search? false
      ]
    ]
    direction-turtle = "up" and dirx = "right"
    [
      set heading 90
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "right"
        set continue-search? false
      ]
    ]
    direction-turtle = "down" and dirx = "left"
    [

      set heading 270
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "left"
        set continue-search? false
      ]
    ]
    direction-turtle = "down" and dirx = "right"
    [

      set heading 90
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "right"
        set continue-search? false
      ]
    ]
    direction-turtle = "left" and diry = "up"
    [

      set heading 0
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "up"
        set continue-search? false
      ]
    ]
    direction-turtle = "left" and diry = "down"
    [

      set heading 180
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "down"
        set continue-search? false
      ]
    ]
    direction-turtle = "right" and diry = "up"
    [

      set heading 0
      if not any? cars-on patch-ahead 1 [
        move-to patch-ahead 1
        set direction-turtle "up"
        set continue-search? false
      ]
    ]
    direction-turtle = "right" and diry = "down"
    [
      if not any? cars-on patch-ahead 1 [
        set heading 180
        move-to patch-ahead 1
        set direction-turtle "down"
        set continue-search? false
      ]
  ])
end

;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Traffic Lights & Speed ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;


;; have the traffic lights change color if phase equals each intersections' my-phase
to set-signals
  ask intersections with [auto? and phase = floor ((my-phase * ticks-per-cycle) / 100)]
  [
    set green-light-up? (not green-light-up?)
    set-signal-colors
  ]
end

;; This procedure checks the variable green-light-up? at each intersection and sets the
;; traffic lights to have the green light up or the green light to the left.
to set-signal-colors  ;; intersection (patch) procedure
  ifelse green-light-up?
  [
    if dirx = "right" and diry = "down"
    [
      ask patch-at -1 0 [ set pcolor green]
      ask patch-at 0 1 [ set pcolor red ]
    ]
    if dirx = "right" and diry = "up"
    [
      ask patch-at -1 0 [ set pcolor green]
      ask patch-at 0 -1 [ set pcolor red ]
    ]
    if dirx = "left" and diry = "down"
    [
      ask patch-at 1 0 [ set pcolor green]
      ask patch-at 0 1 [ set pcolor red ]
    ]
    if dirx = "left" and diry = "up"
    [
      ask patch-at 1 0 [ set pcolor green]
      ask patch-at 0 -1 [ set pcolor red ]
    ]
  ]
  [
    if dirx = "right" and diry = "down"
    [
      ask patch-at -1 0 [ set pcolor red]
      ask patch-at 0 1 [ set pcolor green ]
    ]
    if dirx = "right" and diry = "up"
    [
      ask patch-at -1 0 [ set pcolor red]
      ask patch-at 0 -1 [ set pcolor green ]
    ]
    if dirx = "left" and diry = "down"
    [
      ask patch-at 1 0 [ set pcolor red]
      ask patch-at 0 1 [ set pcolor green ]
    ]
    if dirx = "left" and diry = "up"
    [
      ask patch-at 1 0 [ set pcolor red]
      ask patch-at 0 -1 [ set pcolor green ]
    ]
  ]
end

;; set the turtles' speed based on whether they are at a red traffic light or the speed of the
;; turtle (if any) on the patch in front of them
to set-car-speed  ;; turtle procedure
  ifelse [pcolor] of patch-here = 15
  [ set speed 0 ]
  [ set-speed]
  ;ifelse up-car?
  ;[ set-speed 0 -1 ]
  ;[ set-speed 1 0 ]

end

;; set the speed variable of the car to an appropriate value (not exceeding the
;; speed limit) based on whether there are cars on the patch in front of thecar
to set-speed  ;; turtle procedure
              ;; get the turtles on the patch in front of the turtle
  let turtles-ahead cars-on patch-ahead 1

  ;; if there are turtles in front of the turtle, slow down
  ;; otherwise, speed up
  ifelse any? turtles-ahead
  [
    ifelse any? (turtles-ahead with [ direction-turtle != [direction-turtle] of myself ])
    [
      set speed 0
    ]
    [
      set speed [speed] of one-of turtles-ahead
      slow-down
    ]
  ]
  [ if [pcolor] of patch-here != red [speed-up] ]
end

;; decrease the speed of the turtle
to slow-down  ;; turtle procedure
  ifelse speed <= 0  ;;if speed < 0
  [ set speed 0 ]
  [ set speed speed - acceleration ]
end

;; increase the speed of the turtle
to speed-up  ;; turtle procedure
  ifelse speed > speed-limit
  [ set speed speed-limit ]
  [ set speed speed + acceleration ]
end

;; set the color of the turtle to a different color based on how fast the turtle is moving
to set-car-color  ;; turtle procedure
  ifelse paid? != false
  [ set color black]
  [ set color red]
end

;; keep track of the number of stopped turtles and the amount of time a turtle has been stopped
;; if its speed is 0
to record-data  ;; turtle procedure
  ifelse speed = 0
  [
    set num-cars-stopped num-cars-stopped + 1
    set wait-time wait-time + 1
  ]
  [ set wait-time 0 ]

  set mean-income mean [income] of cars
  set median-income median [income] of cars
end

;; cycles phase to the next appropriate value
to next-phase
  ;; The phase cycles from 0 to ticks-per-cycle, then starts over.
  set phase phase + 1
  if phase mod ticks-per-cycle = 0
    [ set phase 0 ]
end

;;;;;;;;;;;;;;;;;;;;;;;;
;; Parking procedures ;;
;;;;;;;;;;;;;;;;;;;;;;;;


to park-car ;;turtle procedure
  if ((parked? != true) and (ticks > 15)) [
    (foreach [0 0 1 -1] [1 -1 0 0][ [a b] ->
      if ((member? (patch-at a b) lots) and (not any? cars-at a b))[
        let parking-fee ([fee] of patch-at a b * (park-time / 600))  ;; 600 ticks equal one hour
        ifelse (wtp >= parking-fee)
        [
          set paid? true
          set city-income city-income + parking-fee
        ]
        [
          let fine-probability fine-prob park-time
          ifelse ((parking-offender? = true) and (wtp >= ([fee] of patch-at a b * fines-multiplier)* fine-probability ))
          [
            set paid? false
            set city-loss city-loss + parking-fee
          ]
          [
            ifelse member? patch-at a b lots-checked
            [
              set continue-search? true
            ]
            [
              let lot-identifier [lot-id] of patch-at a b ;; value of lot-variable for cur
              let current-lot lots with [lot-id = lot-identifier]
              set lots-checked (patch-set lots-checked current-lot)
              set continue-search? true
              update-wtp
            ]
            stop
          ]
        ]
        set-car-color
        move-to patch-at a b
        set parked? true
        set hasparked? true
        set looksforparking? false
        set nav-prklist []
        set nav-hastarget? false
        set fee-income-share (parking-fee / (income / 12))
        ask patch-at a b [set car? true]
        set lots-checked no-patches
        stop
      ]
      ]
    )
  ]
end

to unpark-car ;; turtle procedure
  ifelse (time-parked < park-time)[
    set time-parked time-parked + 1
  ]
  [
    (foreach [0 0 1 -1] [-1 1 0 0] [[a b]->
      if ((member? patch-at a b roads) and (not any? cars-at a b))[
        set direction-turtle [direction] of patch-at a b
        set heading (ifelse-value
          direction-turtle = "up" [ 0 ]
          direction-turtle = "down"[ 180 ]
          direction-turtle = "left" [ 270 ]
          direction-turtle = "right"[ 90 ])
        move-to patch-at a b
        set parked? false
        set park 0
        set just-parked-countdown 10
        set time-parked 0
        set park-time 300 + random 30000
        set paid? true
        set-car-color
        set reinitialize? true
        ask patch-here[
          set car? false
        ]
        stop
      ]
    ])
  ]
End

;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Environment procedures ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;

to decrease-parked-countdown ;; turtle procedure
  if (just-parked-countdown > 0)[
    set just-parked-countdown just-parked-countdown - 1
  ]
End

to check-park-prob ;; turtle procedure
  if (ticks mod 300 = 0) [
    set park random 100
  ]
End

to update-fees;;
  if (ticks mod 300 = 0) [
    foreach sort  lots [ lot ->
      let lot-color [pcolor] of lot
      let current-lot lots with [pcolor = lot-color]
      let occupancy (count turtles-on current-lot / count current-lot)
      if occupancy > 0.6 [
        ask lot [
          set fee fee + 0.5
        ]
      ]
      if occupancy < 0.25 and [fee] of lot >= 1 [ ask lot [
        set fee fee - 0.5
        ]
      ]
    ]
  ]
End

to update-wtp ;;
  let lot-identifier [lot-id] of one-of lots
  let check-budget (count lots with [lot-id = lot-identifier]) * 4
  let n-checked count lots-checked
  (ifelse
    (n-checked >= check-budget * 0.25) and (n-checked <= check-budget * 0.5)  [
      set wtp wtp + wtp * .05
    ]
    n-checked >= check-budget[ ;; threshold
      die
  ])
End

to recreate-cars;;
  create-cars cars-to-create
  [
    set reinitialize? true
    setup-cars
    set-car-color
    record-data
    if park < 25 [
      set nav-prklist []
      set reinitialize? true
    ]
  ]
  set cars-to-create 0
End

to update-search-time
  if not parked?
  [set search-time search-time + 1]

  ;; output-print search-time
end

to control-lots
  if (ticks mod (600 / controls-per-hour) = 0) [
    let switch random 4
    (ifelse
      switch = 0 [
        let potential-offenders cars-on yellow-lot
        let fines (count potential-offenders with [color = false]) *  fines-multiplier * mean [fee] of yellow-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
      ]
      switch = 1 [
        let potential-offenders cars-on green-lot
        let fines (count potential-offenders with [paid? = false]) * fines-multiplier * mean [fee] of green-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
      ]
      switch = 2 [
        let potential-offenders cars-on orange-lot
        let fines (count potential-offenders with [paid? = false]) * fines-multiplier * mean [fee] of orange-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
      ]
      switch = 3[
        let potential-offenders cars-on blue-lot
        let fines (count potential-offenders with [paid? = false]) * fines-multiplier * mean [fee] of blue-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
    ])
  ]
End

to-report fine-prob [parking-time] ;;computes probabilty to get caught for parking-offenders
  let n-controls round(parking-time / (600 / controls-per-hour))
  ifelse n-controls <= 1 [
    report 0.25
  ]
  [
    let prob 0.25
    while [n-controls > 1][
      set prob prob + (0.75 ^ (n-controls - 1) * 0.25)
      set n-controls n-controls - 1
    ]
    report prob
  ]
end


;;;;;;;;;;;;;;;;;;;;;;
;; Income Reporter ;;
;;;;;;;;;;;;;;;;;;;;;;

;; global reporter: draws a random income, based on the distribution provided by the user
to-report draw-income
  let sigma  sqrt (2 * ln (pop-mean-income / pop-median-income))
  let mu     (ln pop-median-income)
  report exp random-normal mu sigma
end

to-report draw-sampled-income ;;global reporter, draws a random income based on the distribution in the sample
  let sigma  sqrt (2 * ln (mean-income / median-income))
  let mu     (ln median-income)
  report exp random-normal mu sigma
end


to-report find-income-grade ;;check borders
  let sigma sqrt (2 * ln (pop-mean-income / pop-median-income))
  if income > (pop-mean-income + pop-mean-income * sigma * 1)
  [
    report "1"
  ]
  if income > (pop-mean-income - pop-mean-income * sigma * 1) and income <= (pop-mean-income + pop-mean-income * sigma * 1)
  [
    report "2"
  ]
  if income <= (pop-mean-income - pop-mean-income * sigma * 1)
  [
    report "3"
  ]


end

; Copyright 2003 Uri Wilensky.
; See Info tab for full copyright and license.
@#$#@#$#@
GRAPHICS-WINDOW
378
12
1127
762
-1
-1
7.344
1
9
1
1
1
0
0
0
1
-50
50
-50
50
1
1
1
ticks
30.0

PLOT
2865
795
3302
1178
Average Wait Time of Cars
Time
Average Wait
0.0
100.0
0.0
5.0
true
false
"" ""
PENS
"default" 1.0 0 -16777216 true "" "plot mean [wait-time] of cars"

SLIDER
18
183
299
216
num-cars
num-cars
10
1000
590.0
10
1
NIL
HORIZONTAL

PLOT
1474
78
1879
414
Share of Cars per Income Class
Time
%
0.0
7200.0
0.0
100.0
false
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "plot (count cars with [income-grade = \"1\"] / count cars) * 100"
"Middle Income" 1.0 0 -13791810 true "" "plot (count cars with [income-grade = \"2\"] / count cars) * 100"
"Low Income" 1.0 0 -2674135 true "" "plot (count cars with [income-grade = \"3\"] / count cars) * 100"

BUTTON
171
75
302
111
Go
go
T
1
T
OBSERVER
NIL
NIL
NIL
NIL
0

BUTTON
19
75
152
108
Setup
setup
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

SLIDER
23
274
177
307
ticks-per-cycle
ticks-per-cycle
1
100
20.0
1
1
NIL
HORIZONTAL

SLIDER
15
708
199
741
blue-lot-fee
blue-lot-fee
0
20
2.5
0.5
1
€ / hour
HORIZONTAL

SLIDER
14
548
200
581
yellow-lot-fee
yellow-lot-fee
0
20
2.5
0.5
1
€ / hour
HORIZONTAL

SLIDER
17
654
202
687
green-lot-fee
green-lot-fee
0
20
2.5
0.5
1
€ / hour
HORIZONTAL

SLIDER
19
600
204
633
orange-lot-fee
orange-lot-fee
0
20
2.5
0.5
1
€ / hour
HORIZONTAL

PLOT
1473
791
1884
1166
Utilized Capacity at Different Lots
Time
Utilized Capacity in %
0.0
7200.0
0.0
100.0
false
true
"set-plot-background-color grey - 2\n" ""
PENS
"Blue Lot" 1.0 0 -11033397 true "" "plot (count cars-on blue-lot / count blue-lot) * 100"
"Yellow Lot" 1.0 0 -1184463 true "" "plot (count cars-on yellow-lot / count yellow-lot) * 100"
"Green Lot" 1.0 0 -13840069 true "" "plot (count cars-on green-lot / count green-lot) * 100"
"Orange Lot" 1.0 0 -955883 true "" "plot (count cars-on orange-lot / count orange-lot) * 100"

MONITOR
213
1070
348
1115
Mean Income in Model
mean [income] of cars
2
1
11

SLIDER
16
1071
197
1104
pop-median-income
pop-median-income
10000
40000
22713.0
1
1
€
HORIZONTAL

SLIDER
16
1025
197
1058
pop-mean-income
pop-mean-income
0
50000
25882.0
1
1
€
HORIZONTAL

PLOT
1904
791
2368
1174
City Finances
Time
Euro
0.0
7200.0
0.0
10.0
true
true
"" ""
PENS
"Income" 1.0 0 -16777216 true "" "plot city-income"
"Lost Revenue" 1.0 0 -2674135 true "" "plot city-loss"
"Fines paid" 1.0 0 -13791810 true "" "plot total-fines"

SLIDER
14
1118
196
1151
wtp-income-share
wtp-income-share
0
1
0.005
0.001
1
NIL
HORIZONTAL

TEXTBOX
57
499
161
521
Initial Fees
15
0.0
1

MONITOR
254
705
332
750
blue-lot-fee
mean [fee] of blue-lot
17
1
11

MONITOR
252
544
331
589
yellow-lot-fee
mean [fee] of yellow-lot
17
1
11

MONITOR
254
650
336
695
green-lot-fee
mean [fee] of green-lot
17
1
11

MONITOR
252
598
335
643
orange-lot-fee
mean [fee] of orange-lot
17
1
11

TEXTBOX
249
501
334
520
Current Fees
15
0.0
1

PLOT
2380
434
2810
730
Descriptive Income Statistics
Time
Euro
0.0
7200.0
0.0
32000.0
false
true
"" ""
PENS
"Mean" 1.0 0 -16777216 true "" "plot mean-income"
"Median" 1.0 0 -2674135 true "" "plot median-income"
"Standard Deviation" 1.0 0 -13791810 true "" "plot standard-deviation [income] of cars "

PLOT
1473
428
1881
727
Average Search Time per Income Class
Time
Time
0.0
7200.0
0.0
1500.0
false
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "plot mean [search-time] of cars with [income-grade = \"1\"]"
"Middle Income" 1.0 0 -13791810 true "" "plot mean [search-time] of cars with [income-grade = \"2\"]"
"Low Income" 1.0 0 -2674135 true "" "plot mean [search-time] of cars with [income-grade = \"3\"]"

TEXTBOX
99
981
290
1031
Income Distribution
20
0.0
1

TEXTBOX
128
449
278
474
Parking Fees
20
0.0
1

TEXTBOX
123
134
273
159
Traffic Grid
20
0.0
1

SWITCH
188
272
317
305
hide-nodes
hide-nodes
0
1
-1000

SLIDER
21
350
267
383
lot-distribution-percentage
lot-distribution-percentage
0
100
100.0
1
1
%
HORIZONTAL

MONITOR
213
1020
348
1065
Min Income in Model
min [income] of cars
2
1
11

MONITOR
213
1124
347
1169
Max Income in Model
Max [income] of cars
2
1
11

SWITCH
190
313
322
346
show-goals
show-goals
1
1
-1000

PLOT
1892
79
2364
416
Share of parked Cars per Income Class
Time
%
0.0
7200.0
0.0
100.0
false
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "plot (count cars with [parked? = true and income-grade = \"1\"] / count cars with [parked? = true]) * 100"
"Middle Income" 1.0 0 -13791810 true "" "plot (count cars with [parked? = true and income-grade = \"2\"] / count cars with [parked? = true]) * 100"
"Low Income" 1.0 0 -2674135 true "" "plot (count cars with [parked? = true and income-grade = \"3\"] / count cars with [parked? = true]) * 100"

SLIDER
50
840
245
873
fines-multiplier
fines-multiplier
1
20
5.0
1
1
time(s)
HORIZONTAL

TEXTBOX
43
797
309
833
How high should the fines be in terms of the original hourly fee?
13
0.0
1

PLOT
1894
429
2368
726
Fee as Share of Monthly Income per Income Class
Time
%
0.0
7200.0
0.0
2.0
false
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "plot mean [fee-income-share] of cars with [parked? = true and income-grade = \"1\"] * 100"
"Middle Income" 1.0 0 -13791810 true "" "plot mean [fee-income-share] of cars with [parked? = true and income-grade = \"2\"] * 100"
"Low Income" 1.0 0 -2674135 true "" "if count cars with [parked? = true and income-grade = \"3\"] != 0 [plot mean [fee-income-share] of cars with [parked? = true and income-grade = \"3\"] * 100]"

MONITOR
1777
157
1877
202
Number of Cars
count cars
17
1
11

TEXTBOX
2022
37
2172
62
Social Indicators
20
0.0
1

PLOT
2378
79
2810
419
Share of Income Class on Yellow Lot
Time
%
0.0
7200.0
0.0
100.0
false
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "plot (count cars with [([pcolor] of patch-here = yellow) and income-grade = \"1\"] / count cars-on yellow-lot) * 100"
"Middle Income" 1.0 0 -13791810 true "" "plot (count cars with [([pcolor] of patch-here = yellow) and income-grade = \"2\"] / count cars-on yellow-lot) * 100"
"Low Income" 1.0 0 -2674135 true "" "plot (count cars with [([pcolor] of patch-here = yellow) and income-grade = \"3\"] / count cars-on yellow-lot) * 100"

TEXTBOX
1965
757
2269
801
Traffic and Financial Indicators
20
0.0
1

TEXTBOX
44
886
284
934
How often every hour should one of the lots be controlled?
13
0.0
1

SLIDER
45
932
254
965
controls-per-hour
controls-per-hour
1
8
1.0
1
1
time(s)
HORIZONTAL

PLOT
2394
791
2812
1177
Dynamic Fee of Different Lots
Time
Euro
0.0
7200.0
0.0
10.0
false
true
"set-plot-background-color grey - 2" ""
PENS
"Yellow Lot" 1.0 0 -1184463 true "" "plot mean [fee] of yellow-lot"
"Orange Lot" 1.0 0 -955883 true "" "plot mean [fee] of orange-lot"
"Green Lot" 1.0 0 -10899396 true "" "plot mean [fee] of green-lot"
"Blue Lot" 1.0 0 -11033397 true "" "plot mean [fee] of blue-lot"

SWITCH
187
232
335
265
demo-mode
demo-mode
1
1
-1000

@#$#@#$#@
@#$#@#$#@
default
true
0
Polygon -7500403 true true 150 5 40 250 150 205 260 250

airplane
true
0
Polygon -7500403 true true 150 0 135 15 120 60 120 105 15 165 15 195 120 180 135 240 105 270 120 285 150 270 180 285 210 270 165 240 180 180 285 195 285 165 180 105 180 60 165 15

arrow
true
0
Polygon -7500403 true true 150 0 0 150 105 150 105 293 195 293 195 150 300 150

box
false
0
Polygon -7500403 true true 150 285 285 225 285 75 150 135
Polygon -7500403 true true 150 135 15 75 150 15 285 75
Polygon -7500403 true true 15 75 15 225 150 285 150 135
Line -16777216 false 150 285 150 135
Line -16777216 false 150 135 15 75
Line -16777216 false 150 135 285 75

bug
true
0
Circle -7500403 true true 96 182 108
Circle -7500403 true true 110 127 80
Circle -7500403 true true 110 75 80
Line -7500403 true 150 100 80 30
Line -7500403 true 150 100 220 30

butterfly
true
0
Polygon -7500403 true true 150 165 209 199 225 225 225 255 195 270 165 255 150 240
Polygon -7500403 true true 150 165 89 198 75 225 75 255 105 270 135 255 150 240
Polygon -7500403 true true 139 148 100 105 55 90 25 90 10 105 10 135 25 180 40 195 85 194 139 163
Polygon -7500403 true true 162 150 200 105 245 90 275 90 290 105 290 135 275 180 260 195 215 195 162 165
Polygon -16777216 true false 150 255 135 225 120 150 135 120 150 105 165 120 180 150 165 225
Circle -16777216 true false 135 90 30
Line -16777216 false 150 105 195 60
Line -16777216 false 150 105 105 60

car
true
0
Polygon -7500403 true true 180 15 164 21 144 39 135 60 132 74 106 87 84 97 63 115 50 141 50 165 60 225 150 285 165 285 225 285 225 15 180 15
Circle -16777216 true false 180 30 90
Circle -16777216 true false 180 180 90
Polygon -16777216 true false 80 138 78 168 135 166 135 91 105 106 96 111 89 120
Circle -7500403 true true 195 195 58
Circle -7500403 true true 195 47 58

circle
false
0
Circle -7500403 true true 0 0 300

circle 2
false
0
Circle -7500403 true true 0 0 300
Circle -16777216 true false 30 30 240

cow
false
0
Polygon -7500403 true true 200 193 197 249 179 249 177 196 166 187 140 189 93 191 78 179 72 211 49 209 48 181 37 149 25 120 25 89 45 72 103 84 179 75 198 76 252 64 272 81 293 103 285 121 255 121 242 118 224 167
Polygon -7500403 true true 73 210 86 251 62 249 48 208
Polygon -7500403 true true 25 114 16 195 9 204 23 213 25 200 39 123

cylinder
false
0
Circle -7500403 true true 0 0 300

dot
false
0
Circle -7500403 true true 90 90 120

face happy
false
0
Circle -7500403 true true 8 8 285
Circle -16777216 true false 60 75 60
Circle -16777216 true false 180 75 60
Polygon -16777216 true false 150 255 90 239 62 213 47 191 67 179 90 203 109 218 150 225 192 218 210 203 227 181 251 194 236 217 212 240

face neutral
false
0
Circle -7500403 true true 8 7 285
Circle -16777216 true false 60 75 60
Circle -16777216 true false 180 75 60
Rectangle -16777216 true false 60 195 240 225

face sad
false
0
Circle -7500403 true true 8 8 285
Circle -16777216 true false 60 75 60
Circle -16777216 true false 180 75 60
Polygon -16777216 true false 150 168 90 184 62 210 47 232 67 244 90 220 109 205 150 198 192 205 210 220 227 242 251 229 236 206 212 183

fish
false
0
Polygon -1 true false 44 131 21 87 15 86 0 120 15 150 0 180 13 214 20 212 45 166
Polygon -1 true false 135 195 119 235 95 218 76 210 46 204 60 165
Polygon -1 true false 75 45 83 77 71 103 86 114 166 78 135 60
Polygon -7500403 true true 30 136 151 77 226 81 280 119 292 146 292 160 287 170 270 195 195 210 151 212 30 166
Circle -16777216 true false 215 106 30

flag
false
0
Rectangle -7500403 true true 60 15 75 300
Polygon -7500403 true true 90 150 270 90 90 30
Line -7500403 true 75 135 90 135
Line -7500403 true 75 45 90 45

flower
false
0
Polygon -10899396 true false 135 120 165 165 180 210 180 240 150 300 165 300 195 240 195 195 165 135
Circle -7500403 true true 85 132 38
Circle -7500403 true true 130 147 38
Circle -7500403 true true 192 85 38
Circle -7500403 true true 85 40 38
Circle -7500403 true true 177 40 38
Circle -7500403 true true 177 132 38
Circle -7500403 true true 70 85 38
Circle -7500403 true true 130 25 38
Circle -7500403 true true 96 51 108
Circle -16777216 true false 113 68 74
Polygon -10899396 true false 189 233 219 188 249 173 279 188 234 218
Polygon -10899396 true false 180 255 150 210 105 210 75 240 135 240

house
false
0
Rectangle -7500403 true true 45 120 255 285
Rectangle -16777216 true false 120 210 180 285
Polygon -7500403 true true 15 120 150 15 285 120
Line -16777216 false 30 120 270 120

leaf
false
0
Polygon -7500403 true true 150 210 135 195 120 210 60 210 30 195 60 180 60 165 15 135 30 120 15 105 40 104 45 90 60 90 90 105 105 120 120 120 105 60 120 60 135 30 150 15 165 30 180 60 195 60 180 120 195 120 210 105 240 90 255 90 263 104 285 105 270 120 285 135 240 165 240 180 270 195 240 210 180 210 165 195
Polygon -7500403 true true 135 195 135 240 120 255 105 255 105 285 135 285 165 240 165 195

line
true
0
Line -7500403 true 150 0 150 300

line half
true
0
Line -7500403 true 150 0 150 150

pentagon
false
0
Polygon -7500403 true true 150 15 15 120 60 285 240 285 285 120

person
false
0
Circle -7500403 true true 110 5 80
Polygon -7500403 true true 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Rectangle -7500403 true true 127 79 172 94
Polygon -7500403 true true 195 90 240 150 225 180 165 105
Polygon -7500403 true true 105 90 60 150 75 180 135 105

plant
false
0
Rectangle -7500403 true true 135 90 165 300
Polygon -7500403 true true 135 255 90 210 45 195 75 255 135 285
Polygon -7500403 true true 165 255 210 210 255 195 225 255 165 285
Polygon -7500403 true true 135 180 90 135 45 120 75 180 135 210
Polygon -7500403 true true 165 180 165 210 225 180 255 120 210 135
Polygon -7500403 true true 135 105 90 60 45 45 75 105 135 135
Polygon -7500403 true true 165 105 165 135 225 105 255 45 210 60
Polygon -7500403 true true 135 90 120 45 150 15 180 45 165 90

square
false
0
Rectangle -7500403 true true 30 30 270 270

square 2
false
0
Rectangle -7500403 true true 30 30 270 270
Rectangle -16777216 true false 60 60 240 240

star
false
0
Polygon -7500403 true true 151 1 185 108 298 108 207 175 242 282 151 216 59 282 94 175 3 108 116 108

target
false
0
Circle -7500403 true true 0 0 300
Circle -16777216 true false 30 30 240
Circle -7500403 true true 60 60 180
Circle -16777216 true false 90 90 120
Circle -7500403 true true 120 120 60

tree
false
0
Circle -7500403 true true 118 3 94
Rectangle -6459832 true false 120 195 180 300
Circle -7500403 true true 65 21 108
Circle -7500403 true true 116 41 127
Circle -7500403 true true 45 90 120
Circle -7500403 true true 104 74 152

triangle
false
0
Polygon -7500403 true true 150 30 15 255 285 255

triangle 2
false
0
Polygon -7500403 true true 150 30 15 255 285 255
Polygon -16777216 true false 151 99 225 223 75 224

truck
false
0
Rectangle -7500403 true true 4 45 195 187
Polygon -7500403 true true 296 193 296 150 259 134 244 104 208 104 207 194
Rectangle -1 true false 195 60 195 105
Polygon -16777216 true false 238 112 252 141 219 141 218 112
Circle -16777216 true false 234 174 42
Rectangle -7500403 true true 181 185 214 194
Circle -16777216 true false 144 174 42
Circle -16777216 true false 24 174 42
Circle -7500403 false true 24 174 42
Circle -7500403 false true 144 174 42
Circle -7500403 false true 234 174 42

turtle
true
0
Polygon -10899396 true false 215 204 240 233 246 254 228 266 215 252 193 210
Polygon -10899396 true false 195 90 225 75 245 75 260 89 269 108 261 124 240 105 225 105 210 105
Polygon -10899396 true false 105 90 75 75 55 75 40 89 31 108 39 124 60 105 75 105 90 105
Polygon -10899396 true false 132 85 134 64 107 51 108 17 150 2 192 18 192 52 169 65 172 87
Polygon -10899396 true false 85 204 60 233 54 254 72 266 85 252 107 210
Polygon -7500403 true true 119 75 179 75 209 101 224 135 220 225 175 261 128 261 81 224 74 135 88 99

wheel
false
0
Circle -7500403 true true 3 3 294
Circle -16777216 true false 30 30 240
Line -7500403 true 150 285 150 15
Line -7500403 true 15 150 285 150
Circle -7500403 true true 120 120 60
Line -7500403 true 216 40 79 269
Line -7500403 true 40 84 269 221
Line -7500403 true 40 216 269 79
Line -7500403 true 84 40 221 269

x
false
0
Polygon -7500403 true true 270 75 225 30 30 225 75 270
Polygon -7500403 true true 30 75 75 30 270 225 225 270
@#$#@#$#@
NetLogo 6.1.1
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
default
0.0
-0.2 0 0.0 1.0
0.0 1 1.0 0.0
0.2 0 0.0 1.0
link direction
true
0
Line -7500403 true 150 150 90 180
Line -7500403 true 150 150 210 180
@#$#@#$#@
0
@#$#@#$#@
