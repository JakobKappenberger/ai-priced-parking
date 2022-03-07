extensions [nw csv]

breed [nodes node]
breed [cars car]


globals
[
  grid-x-inc               ;; the amount of patches in between two roads in the x direction
  grid-y-inc               ;; the amount of patches in between two roads in the y direction
  acceleration             ;; the constant that controls how much a car speeds up or slows down by if
                           ;; it is to accelerate or decelerate
  intersec-max-x           ;; outer coordinates of intersections (required to set-up lots and garages)
  intersec-min-x
  intersec-max-y
  intersec-min-y

  speed-limit              ;; the maximum speed of the cars
  phase                    ;; keeps track of the phase (traffic lights)
  num-cars-stopped         ;; the number of cars that are stopped during a single pass thru the go procedure
  city-income              ;; money the city currently makes
  city-loss                ;; money the city loses because people do not buy tickets
  total-fines              ;; sum of all fines collected by the city
  lot-counter              ;; counter for id assigment
  num-spaces               ;; number of individual spaces
  n-cars                   ;; number of currently active cars
  mean-wait-time           ;; average wait time of cars
  yellow-lot-current-fee   ;; current fee of yellow
  green-lot-current-fee   ;; current fee of green
  teal-lot-current-fee    ;; current fee of teal
  blue-lot-current-fee     ;; current fee of blue
  potential-goals          ;; agents with all building patches

  yellow-lot-current-occup   ;; current occupation of yellow
  green-lot-current-occup   ;; current occupation of green
  teal-lot-current-occup    ;; current occupation of teal
  blue-lot-current-occup     ;; current occupation of blue
  garages-current-occup

  vanished-cars-poor        ;; counter for cars that are not respawned
  vanished-cars-middle
  vanished-cars-rich

  global-occupancy         ;; overall occupancy of all lots
  cars-to-create           ;; number of cars that have to be created to replace those leaving the map
  poor-to-create
  middle-to-create
  high-to-create
  mean-income              ;; mean income of turtles
  median-income            ;; median-income of turtles
  color-counter            ;; counter to ensure that every group of lots is visited only twice
  lot-colors               ;; colors to identify different lots

  selected-car   ;; the currently selected car //inserted

  ;; patch agentsets
  intersections ;; agentset containing the patches that are intersections
  roads         ;; agentset containing the patches that are roads
  yellow-lot    ;; agentset containing the patches that contain the spaces for the yellow lot
  teal-lot     ;; agentset containing the patches that contain the spaces for the teal lot
  green-lot    ;; agentset containing the patches that contain the spaces for the green lot
  blue-lot      ;; agentset containing the patches that contain the spaces for the blue lot
  lots          ;; agentset containing all patches that are parking spaces
  gateways      ;; agentset containing all patches that are gateways to garages
  garages       ;; agentset containing all patches that are parking spaces in garages
  finalpatches  ;; agentset containing all patches that are at the end of streets
  initial-spawnpatches ;; agentset containing all patches for initial spawning
  spawnpatches   ;;agentset containing all patches that are beginning of streets
  traffic-counter ;; counter to calibrate model to resemble subject as closely as possible
  income-entropy ;; normalized entropy of income-class distribution
  initial-poor  ;; initial share of poor income class
  normalized-share-poor ;;
  mean-speed ;; average speed of cars not parking
  share-cruising ;; share of cars crusing
]

nodes-own
[

]
cars-own
[
  wait-time ;; time passed since a turtle has moved

  speed         ;; the current speed of the car
  park-time     ;; the time the driver wants to stay in the parking-spot
  park          ;; the driver's probability to be searching for a parking space
  paid?         ;; true if the car paid for its spot
  looks-for-parking? ;; whether the agent is currently looking for parking in the target street
  parked?       ;; true if the car is parked
  time-parked     ;; time spent parking
  income          ;; income of agent
  wtp             ;; Willigness to Pay for parking
  wtp-increased   ;; counter to keep track of how often the wtp was increased when searching
  parking-offender? ;; boolean for parking offenders
  lots-checked     ;; patch-set of lots checked by the driver
  direction-turtle ;; turtle dircetion
  nav-goal         ;; objective of turtle on the map
  nav-prklist      ;; list of parking spots sorted by distance to nav-goal
  nav-hastarget?   ;; boolean to check if agent has objective
  nav-pathtofollow ;; list of nodes to follow
  income-grade     ;; ordinial classification of income
  search-time    ;; time to find a parking space
  reinitialize? ;; for agents who have left the map
  die?
  fee-income-share ;; fee as a portion of income
  distance-parking-target ;; distance from parking to target
  price-paid       ;; price paid for pricing
  expected-fine    ;; expected fine for parking offender
  outcome          ;; outcome of agents (depends on access and agress, price-paid, etc.)

]

patches-own
[
  road?           ;; true if the patch is a road
  horizontal?     ;; true for road patches that are horizontal; false for vertical roads
                  ;;-1 for non-road patches
  alternate-direction? ;; true for every other parallel road.
                       ;;-1 for non-road patches
  direction       ;; one of "up", "down", "left" or "right"
                  ;;-1 for non-road patches
  intersection?   ;; true if the patch is at the intersection of two roads
  park-intersection? ;; true if the intersection has parking spaces
  dirx
  diry
  green-light-up? ;; true if the green light is above the intersection.  otherwise, false.
                  ;; false for a non-intersection patches.
  my-row          ;; the row of the intersection counting from the upper left corner of the
                  ;; world.  -1 for non-intersection and non-horizontal road patches.
  my-column       ;; the column of the intersection counting from the upper left corner of the
                  ;; world.  -1 for non-intersection and non-vertical road patches.
  my-phase        ;; the phase for the intersection.  -1 for non-intersection patches.
  car?            ;; whether there is a car on this patch
  fee             ;; price of parking here
  lot-id          ;; id of lot
  center-distance ;; distance to center of map
  garage?         ;; true for private garages
  gateway?        ;; true for gateways of garages
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
  set speed-limit 0.9  ;;speed required for somewhat accurate representation

  ;; First we ask the patches to draw themselves and set up a few variables
  setup-patches

  set-default-shape cars "car top"

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
    ifelse park <= parking-cars-percentage [
      setup-parked
      set reinitialize? true
    ]
    [
      set nav-prklist [] ;; let the rest leave the map
      set reinitialize? true
    ]
  ]
  if ((count cars with [park <= parking-cars-percentage]) / num-spaces) < target-start-occupancy
  [
    user-message (word "There are not enough cars to meet the specified "
      "start target occupancy rate.  Either increase the number of roads "
      ", or decrease the "
      "number of parking spaces by by lowering the lot-distribution-percentage slider.")
  ]

  ;; give the turtles an initial speed
  ask cars [ set-car-speed ]

  if demo-mode [ ;; for demonstration purposes
    let example_car one-of cars with [park > parking-cars-percentage and not parked?]
    ask example_car [
      set color cyan
      set nav-prklist navigate patch-here nav-goal
      set park parking-cars-percentage / 2
    ]
    watch example_car
    inspect example_car
    ask [nav-goal] of example_car [set pcolor cyan]
  ]

  ;; for Reinforcement Learning reward function
  set initial-poor count cars with [income-grade = 0] / count cars

  record-globals
  reset-ticks
  ;; for documentation of all agents at every timestep
  if document-turtles [
    file-open output-turtle-file-path
    file-print csv:to-row (list "id" "income" "income-group" "wtp" "parking-offender?" "distance-parking-target" "price-paid" "search-time" "wants-to-park" "die?" "reinitialize?")
  ]
end

to setup-finalroads
  set finalpatches roads with [(pxcor = max-pxcor and direction = "right") or (pxcor = min-pxcor and direction = "left") or (pycor  = max-pycor and direction = "up") or (pycor = min-pycor and direction = "down") ]

end

to setup-spawnroads
  set spawnpatches roads; with [(pxcor = max-pxcor and direction = "left") or (pxcor = min-pxcor and direction = "right") or (pycor  = max-pycor and direction = "down") or (pycor = min-pycor and direction = "up") ]
end

;; spawn intial cars so that they can navigate over the map
to setup-initial-spawnroads
  set initial-spawnpatches roads with [not intersection?]
end



;; Initialize the global variables to appropriate values
to setup-globals
  set phase 0
  set num-cars-stopped 0
  set grid-x-inc 15
  set grid-y-inc floor(grid-x-inc * 1.43) ;; x*1,43 is the Relation of the Mannheim quadrate but 1.2 looks nicer

  set n-cars num-cars

  set vanished-cars-poor 0
  set vanished-cars-middle 0
  set vanished-cars-rich 0
  set traffic-counter 0

  set mean-income 0
  set median-income 0
  set n-cars 0
  set mean-wait-time 0
  set mean-speed 0

  set yellow-lot-current-fee 0
  set green-lot-current-fee 0
  set teal-lot-current-fee 0
  set blue-lot-current-fee 0

  set global-occupancy 0

  set yellow-lot-current-occup 0
  set green-lot-current-occup 0
  set teal-lot-current-occup 0
  set blue-lot-current-occup 0
  if num-garages > 0 [set garages-current-occup 0]
  set income-entropy 0
  set initial-poor 0
  set normalized-share-poor 0
  set share-cruising 0

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
    set green-light-up? true
    set my-row -1
    set my-column -1
    set my-phase -1
    set pcolor brown + 3
    set center-distance [distancexy 0 0] of self
  ]

  ;; initialize the global variables that hold patch agentsets

  set roads patches with
    [(floor((pxcor + max-pxcor - floor(grid-x-inc - 1)) mod grid-x-inc) = 8) or
      (floor((pycor + max-pycor) mod grid-y-inc) = 8)]
  setup-roads
  set intersections roads with
    [(floor((pxcor + max-pxcor - floor(grid-x-inc - 1)) mod grid-x-inc) = 8) and
      (floor((pycor + max-pycor) mod grid-y-inc) = 8)]

  set intersec-max-x max [pxcor] of intersections
  set intersec-min-x min [pxcor] of intersections
  set intersec-max-y max [pycor] of intersections
  set intersec-min-y min [pycor] of intersections

  setup-intersections
  setup-lots
  if num-garages > 0 [setup-garages]
  setup-finalroads
  setup-spawnroads
  setup-initial-spawnroads
  setup-nodes

  ;; all non-road patches can become goals
  set potential-goals patches with [pcolor = brown + 3]
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


    sprout-nodes 1 [ ;; node network for navigation
      set size 0.2
      set shape "circle"
      set color white
    ]


  ]
end

to setup-nodes
  ask nodes [
    (ifelse
      dirx = "left" [create-links-to nodes-on patch-at -1 0[set hidden? hide-nodes]]
      dirx = "right" [create-links-to nodes-on patch-at 1 0[set hidden? hide-nodes] ])

    (ifelse
      diry = "up" [create-links-to nodes-on patch-at 0 1[set hidden? hide-nodes]]
      diry = "down" [create-links-to nodes-on patch-at 0 -1[set hidden? hide-nodes] ])
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
  set lot-counter 1
  ask intersections [set park-intersection? false]

  let potential-intersections intersections
  ask n-of (count potential-intersections * lot-distribution-percentage) potential-intersections [set park-intersection? true] ;; create as many parking lots as specified by lot-distribution-percentage  variable
                                                                                                                               ;; check if there is enough space for garages
  let garage-intersections intersections with [not park-intersection? and pxcor != intersec-max-x and pycor != intersec-min-y and pycor != intersec-min-y + grid-y-inc] ;; second intersec from down-left cannot be navigated
  if num-garages > 0 and num-garages > count garage-intersections[
    user-message (word "There are not enough free intersections to create the garages. "
      "Decrease the lot-occupancy to create the neccessary space. "
      "For this simulation, the number of on-street lots will be decreased.")
    ask n-of (num-garages) intersections with [park-intersection? = true and pxcor != intersec-max-x and pycor != intersec-min-y and pycor != intersec-min-y + grid-y-inc] [
      set park-intersection? false
    ]
  ]
  ask intersections with [park-intersection? = true][
    let x [pxcor] of self
    let y [pycor] of self
    if x != intersec-max-x and x != intersec-min-x and y != intersec-max-y and y != intersec-min-y [ ;;lots at the beginning and end of grid do not work with navigation
      spawn-lots x y "all"
    ]
    if x = intersec-min-x and y != intersec-min-y [ ;; create all possible lots on the right for the intersections that are on the left border
      spawn-lots x y "all"
    ]
    if x = intersec-max-x and y != intersec-min-y and y != intersec-max-y [ ;; create only down lots for the intersections that are on the right border
      spawn-lots x y "down"
    ]
    if y = intersec-max-y and x != intersec-max-x and x != intersec-min-x [ ;; create all lots below for the intersections that are on the upper border
      spawn-lots x y "all"
    ]
    if y = intersec-min-y and x < intersec-max-x [ ;; create only lower lots for intersections on lower border
      spawn-lots x y "right"
    ]
  ]

  ;; create patch-sets for different parking zones by distance to center of map
  set yellow-lot no-patches
  set green-lot no-patches
  set teal-lot no-patches
  set blue-lot no-patches

  let lot-distances sort remove-duplicates [center-distance] of patches  with [lot-id != 0]
  let lot-count length lot-distances
  let i 0
  foreach lot-distances [lot-distance ->
    if i <= lot-count * 0.1[
      set yellow-lot (patch-set yellow-lot patches with [lot-id != 0 and center-distance = lot-distance])
    ]
    if i > lot-count * 0.1 and i <= lot-count * 0.35[
      set green-lot (patch-set green-lot patches with [lot-id != 0 and center-distance = lot-distance])
    ]
    if i > lot-count * 0.35 and i <= lot-count * 0.6[
      set teal-lot (patch-set teal-lot patches with [lot-id != 0 and center-distance = lot-distance])
    ]
    if i > lot-count * 0.6[
      set blue-lot (patch-set blue-lot patches with [lot-id != 0 and center-distance = lot-distance])
    ]
    set i i + 1
  ]

  ;; create patch-set for all parking spaces on the curbside
  set lots (patch-set yellow-lot teal-lot green-lot blue-lot)
  set num-spaces count lots

  ;; color parking zones
  let yellow-c [255.0 254.997195 102.02397]
  ask yellow-lot [
    set pcolor yellow-c
    set fee yellow-lot-fee
  ]
  let green-c [122.92632 173.61190499999998 116.145105]
  ask green-lot [
    set pcolor green-c
    set fee green-lot-fee
  ]
  let teal-c [57.189615 106.713675 147.774285]
  ask teal-lot [
    set pcolor teal-c
    set fee teal-lot-fee
  ]
  let blue-c 	[25.867455 51.02805 178.54946999999999]
  ask blue-lot [
    set pcolor blue-c
    set fee blue-lot-fee
  ]

  set lot-colors (list yellow-c green-c teal-c blue-c) ;; will be used to identify the different zones
end

;; creates lots, specification controls whether only to the right or down of intersection (or both)
to spawn-lots [x y specification] ;;
  let right-lots false
  let down-lots false
  ifelse specification = "all" [
    set right-lots true
    set down-lots true
  ]
  [
    ifelse specification = "right"[
      set right-lots true
    ]
    [
      set down-lots true
    ]
  ]
  if down-lots [
    ifelse random 100 >= 25 [ ;; random variable so that in 75% of cases, parking spots on both sides of road are created
      let potential-lots patches with [((pxcor = x + 1 ) or (pxcor = x - 1)) and ((pycor >= y - ( grid-y-inc * .75)) and (pycor <= y - (grid-y-inc * .25)))]
      let average-distance mean [center-distance] of potential-lots
      ask potential-lots [
        set center-distance average-distance ;;assign lot the average distance of its members
        set lot-id lot-counter
      ]
      set lot-counter lot-counter + 1
    ]
    [
      let random-x ifelse-value (random 100 <= 50) [1] [-1]
      let potential-lots patches with [((pxcor = x + random-x)) and ((pycor >= y - ( grid-y-inc * .75)) and (pycor <= y - (grid-y-inc * .25)))]
      let average-distance mean [center-distance] of potential-lots
      ask potential-lots [
        set center-distance average-distance
        set lot-id lot-counter
      ]
      set lot-counter lot-counter + 1
    ]
  ]
  if right-lots [
    ifelse random 100 >= 25 [
      let potential-lots patches with [((pycor = y + 1 ) or (pycor = y - 1)) and (((pxcor <= x + ( grid-x-inc * .75)) and (pxcor >= x + (grid-x-inc * .25))))]
      let average-distance mean [center-distance] of potential-lots
      ask potential-lots[
        set center-distance average-distance
        set lot-id lot-counter
      ]
      set lot-counter lot-counter + 1
    ]
    [
      let random-y ifelse-value (random 100 <= 50) [1] [-1]
      let potential-lots patches with [(pycor = y + random-y) and (((pxcor <= x + ( grid-x-inc * .75)) and (pxcor >= x + (grid-x-inc * .25))))]
      let average-distance mean [center-distance] of potential-lots
      ask potential-lots [
        set center-distance average-distance
        set lot-id lot-counter
      ]
      set lot-counter lot-counter + 1
    ]
  ]
end

;; create garages
to setup-garages
  ask patches [
    set garage? false
    set gateway? false
  ]
  let garage-intersections n-of (num-garages) intersections with [not park-intersection? and pxcor != intersec-max-x and pycor != intersec-min-y] ;; second intersec from down-left cannot be navigated
  ask garage-intersections[
    let x [pxcor] of self
    let y [pycor] of self
    let dir-intersec [direction] of self
    let potential-garages patches with [(((pxcor <= x + ( grid-x-inc * .7)) and (pxcor >= x + (grid-x-inc * .25)))) and ((pycor >= y - ( grid-y-inc * .7)) and (pycor <= y - (grid-y-inc * .25)))]
    let id (max [lot-id] of patches) + 1
    ask potential-garages [
      set pcolor black
      set direction dir-intersec
      set lot-id id
      set fee 2
      set garage? true
      ask patches with [((pxcor <= x + ( grid-x-inc * .25)) and (pxcor > x )) and (pycor = floor(y - ( grid-y-inc * .5)))] [
        set pcolor black
        if [pxcor] of self = x + 1[
          set gateway? true
          set lot-id id
        ]
      ]
    ]
  ]
  set garages patches with [garage?]
  set gateways patches with [gateway?]
END

;; Initialize the turtle variables to appropriate values and place the turtle on an empty road patch.
to setup-cars  ;; turtle procedure
  set speed 0
  set wait-time 0
  ;; check whether agent is created at beginning of model (reinitialize? = 0) or recreated during run of simulation (reinitialize? = true)
  ifelse reinitialize? = 0 [
    put-on-empty-road
    set income draw-income
    set income-grade find-income-grade
    set park random 100
  ]
  [
    move-to one-of spawnpatches with [not any? cars-on self]
    ;; income of recreated cars is based on the distro of the model
    (ifelse
      poor-to-create > 0 [
        set poor-to-create poor-to-create - 1
        set income-grade 99
        ;; not very efficient, draw until desired income is drawn
        while [income-grade != 0] [
          set income draw-income
          set income-grade find-income-grade
        ]
      ]
      middle-to-create > 0 [
        set middle-to-create middle-to-create - 1
        set income-grade 99
        while [income-grade != 1] [
          set income draw-income
          set income-grade find-income-grade
        ]
      ]
      high-to-create > 0 [
        set high-to-create high-to-create - 1
        set income-grade 99
        while [income-grade != 2] [
          set income draw-income
          set income-grade find-income-grade
        ]
      ]
    )
    ;; keep distro of cars wanting to park in model constant
    (ifelse (count cars with [park <= parking-cars-percentage] * 100 / count cars) > parking-cars-percentage
      [
        set park parking-cars-percentage +  random (100 - parking-cars-percentage)
      ]
      [
        set park random parking-cars-percentage
      ]
    )
  ]

  set direction-turtle [direction] of patch-here
  set looks-for-parking? false
  ;; if placed on intersections, decide orientation randomly
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

  ;; set goals for navigation
  set-navgoal
  set nav-prklist navigate patch-here nav-goal
  set nav-hastarget? false


  set park-time draw-park-duration
  set parked? false
  set reinitialize? true
  set die? false
  set wtp draw-wtp
  set wtp-increased 0

  ;; designate parking offenders (right now 25%)
  let offender-prob random 100
  ifelse offender-prob >= 75  [
    set parking-offender? true
  ]
  [
    set parking-offender? false
  ]

  set lots-checked no-patches

  ;; variables for utility function
  set distance-parking-target -99
  set price-paid -99
  set expected-fine -99
  set outcome -99
end

;; Setup cars before starting simulation so as to hit the target occupancy (if possible)
to setup-parked
  foreach lot-colors [ lot-color ->
    let current-lot lots with [pcolor = lot-color]
    let occupancy (count cars-on current-lot / count current-lot)
    if occupancy < target-start-occupancy [
      let inital-lot one-of current-lot with [not any? cars-on self]
      move-to inital-lot
      ask inital-lot [set car? true]
      set parked? true
      set looks-for-parking? false
      set nav-prklist []
      set nav-hastarget? false
      let parking-fee ([fee] of inital-lot )  ;; compute fee
      set fee-income-share (parking-fee / (income / 12))
      ifelse (wtp >= parking-fee)
      [
        set paid? true
        set price-paid parking-fee
      ]
      [
        set paid? false
      ]
      set-car-color
      set distance-parking-target distance nav-goal ;; update distance to goal (problematic here?)
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
      stop
    ]
  ]
end

;; Find a road patch without any turtles on it and place the turtle there.
to put-on-empty-road  ;; turtle procedure
  move-to one-of initial-spawnpatches with [not any? cars-on self]
end

;; Determine parking lots closest to current goal
to-report navigate [current goal]

  let fav-lots []
  let templots lots
  ;; check if there is any curbside space cheaper than garages and whether the garages are full, otherwise only check curbside parking
  if num-garages > 0[
    let garage-fee mean [fee] of garages
    if (not any? lots with [fee < garage-fee]) and ((count cars-on garages / count garages) < 1)[
      set templots (patch-set lots gateways)
    ]
  ]

  while [count templots > 0] [
    let i min-one-of templots [distance goal]
    set fav-lots insert-item 0 fav-lots [lot-id] of i
    set templots templots with [lot-id != [lot-id] of i]
    set color-counter color-counter + 1
    ;; check two streets per parking zone (otherwise cars search for too long
    if color-counter = 2[
      set templots templots with [pcolor != [pcolor] of i]
      set color-counter 0
    ]
  ]
  set fav-lots reverse fav-lots
  set color-counter 0
  report fav-lots
end

;; assignment of navigation goal for new agents, spots in the center are more likely to become goals
to set-navgoal
  let max-distance max [center-distance] of potential-goals
  let switch random 100
  (ifelse
    switch <= 39 [
      set nav-goal one-of potential-goals with [center-distance <= max-distance * 0.35]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance * 0.35][
          set pcolor cyan
        ]
      ]
    ]
    switch > 39 and switch <= 65 [
      set nav-goal one-of potential-goals with [center-distance <= max-distance * 0.5 and center-distance > max-distance * 0.35]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance * 0.5 and center-distance > max-distance * 0.35][
          set pcolor pink
        ]
      ]
    ]
    switch > 65 and switch <= 80 [
      set nav-goal one-of potential-goals with [center-distance <= max-distance * 0.6 and center-distance > max-distance * 0.5]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance * 0.6 and center-distance > max-distance * 0.5][
          set pcolor violet
        ]
      ]
    ]
    switch > 80[
      set nav-goal one-of potential-goals with [center-distance <= max-distance and center-distance > max-distance * 0.6]
      if show-goals[
        ask one-of potential-goals with [center-distance <= max-distance and center-distance > max-distance * 0.6][
          set pcolor turquoise
        ]
      ]
  ])
end

;;;;;;;;;;;;;;;;;;;;;;;;
;; Runtime Procedures ;;
;;;;;;;;;;;;;;;;;;;;;;;;

;; Run the simulation, is called at every timestep
to go

  ;; have the intersections change their color
  set-signals
  set num-cars-stopped 0

  ;; set the turtles speed for this time thru the procedure, move them forward their speed,
  ;; record data for plotting, and set the color of the turtles to an appropriate color
  ;; based on their speed
  ask cars
  [
    if die? and (patch-ahead 1 = nobody or (member? patch-ahead 1 finalpatches)) [;; if, due to rounding, the car ends up on the final patch or the next patch is a final patch
      set traffic-counter traffic-counter + 1
      if reinitialize? [
        keep-distro income-grade
        set cars-to-create cars-to-create +  1
      ]
      if document-turtles [document-turtle]
      die
    ]

    ifelse not parked?
    [
      ;if car has no target
      if not nav-hastarget?[
        ;; if I have already parked, I can delete my parking list.

        let node-ahead one-of nodes-on patch-ahead 1
        ifelse not empty? nav-prklist
        ; set new path to first element of nav-prklist if not empty
        [
          ifelse node-ahead != nobody [
            set nav-pathtofollow determine-path node-ahead first nav-prklist
          ]
          [
            set nav-pathtofollow determine-path one-of nodes-on patch-here first nav-prklist
          ]
        ] ;; use patch-ahead because otherwise a node behind the car may be chosen, leading it to do a U-turn
          ;; if the parking list is empty either all parkingspots were tried or the car has already parked
        [
          ifelse node-ahead != nobody [
            set nav-pathtofollow determine-finaldestination node-ahead
          ]
          [
            set nav-pathtofollow determine-finaldestination one-of nodes-on patch-here
          ]
          set die? true
        ] ;; use patch-ahead because otherwise a node behind the car may be chosen, leading it to do a U-turn

        set nav-hastarget? true
      ]

      ;; hotfix (should think of better solution)
      if nav-pathtofollow = false [
        show nav-pathtofollow
        show patch-here
        show search-time
        if reinitialize? [
          keep-distro income-grade
          set cars-to-create cars-to-create +  1
        ]
        if document-turtles [document-turtle]
        die
      ]

      ;==================================================
      ifelse not empty? nav-pathtofollow [
        if wait-time > 50 and member? patch-ahead 1 intersections[
          ;; alternative routing to avoid non-dissolvable congestion
          compute-alternative-route
        ]
        let nodex first nav-pathtofollow
        set-car-speed
        let x [xcor] of nodex
        let y [ycor] of nodex
        let patch-node patch x y
        face nodex ;evtl abändern
        set direction-turtle [direction] of patch-node
        fd speed
        if intersection? and not any? cars-on patch-ahead 1 [
          ;in case someoned looked for a parking lot, after reaching the end of a street (=Intersection) he does not look anymore
          set looks-for-parking? false
          move-to nodex
        ]
        ;wenn wir node erreicht haben,
        if one-of nodes-here = nodex [
          ;delete first node from nav-pathtofollow
          set nav-pathtofollow remove-item 0 nav-pathtofollow
        ]
      ]
      [
        ;is looking for parking
        set looks-for-parking? true
        ;car currently has no target
        set nav-hastarget? false
        ; first item from prklist is deleted (has been  visited)
        if not empty? nav-prklist [ ;;Dummy implementation
          set nav-prklist remove-item 0 nav-prklist
        ]
      ]
      ;==================================================
      if park <= parking-cars-percentage and looks-for-parking? ;; x% of cars look for parking
      [
        park-car
      ]
      record-data
      ;;set-car-color
    ]
    [
      unpark-car
    ]
    update-search-time ;;increments search-time if not parked
  ]

  ;; update the phase and the global clock
  control-lots
  ;; set prices dynamically
  if dynamic-pricing-baseline [update-baseline-fees]
  recreate-cars
  record-globals

  next-phase
  tick
end

;;;;;;;;;;;;;;;;
;; Navigation ;;
;;;;;;;;;;;;;;;;


;; plot path to exit
to-report determine-finaldestination [start-node]
  let finalnodes nodes-on finalpatches
  let finalnode min-one-of finalnodes [length(nw:turtles-on-path-to one-of nodes-here)]
  let path 0
  ask start-node [set path nw:turtles-on-path-to finalnode]
  report path
end

;; plot path to parking street
to-report determine-path [start lotID]
  let lotproxy one-of lots with [lot-id = lotID]
  ;; if lot-id belongs to garage, navigate to gateway
  if num-garages > 0 [
    if any? gateways with [lot-id = lotID][
      set lotproxy gateways with [lot-id = lotID]
    ]
  ]
  let node-proxy 0
  ask lotproxy [
    set node-proxy one-of nodes-on neighbors4
  ]

  let previous node-proxy
  ask node-proxy[
    let current one-of in-link-neighbors
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

;; in cases of too much congestion, compute alternative route to destination
to compute-alternative-route
  ;; Check whether intersections lies at the outer border of the map
  let intersec patch-ahead 1
  let x-intersec [pxcor] of intersec
  let y-intersec [pycor] of intersec

  ;; check what alternatives might be available
  let direct-x [dirx] of intersec
  let direct-y [diry] of intersec
  let x (ifelse-value
    direct-x = "left" [-1]
    direct-x = "right" [1]
  )
  let y (ifelse-value
    direct-y = "up" [1]
    direct-y = "down" [-1])


  let nodes-ahead one-of nodes-on patch-ahead 2
  let nodes-turn one-of nodes-on patch-at x y
  let path 0
  ifelse not member? nodes-ahead nav-pathtofollow [
    ifelse nodes-ahead != nobody and not any? cars-on patch-ahead 2[
      ask one-of nodes-on intersec [set path nw:turtles-on-path-to nodes-ahead]
    ]
    [
      stop
    ]
  ]
  [
    ifelse nodes-turn != nobody and not any? cars-on patch-at x y[
      ask one-of nodes-on intersec [set path nw:turtles-on-path-to nodes-turn]
    ]
    [
      stop
    ]
  ]
  ifelse not empty? nav-prklist
  ; set new path to first element of nav-prklist if not empty
  [
    let path-to-parking determine-path last path first nav-prklist
    set nav-pathtofollow remove-duplicates sentence path path-to-parking
  ] ;; use patch-ahead because otherwise a node behind the car may be chosen, leading it to do a U-turn
    ;; if the parking list is empty either all parkingspots were tried or the car has already parked
  [
    let path-to-death determine-finaldestination last path
    set nav-pathtofollow remove-duplicates sentence path path-to-death
  ]
end

;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Traffic Lights & Speed ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;


;; have the traffic lights change color if phase equals each intersections' my-phase
to set-signals
  if phase = 0 [
    ask intersections
    [
      set green-light-up? (not green-light-up?)
      set-signal-colors
    ]
  ]

  if phase >= ticks-per-cycle - ticks-per-cycle * 0.2[
    ask intersections
    [
      set-signal-yellow
    ]
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
      ask patch-at 0 -1 [ set pcolor red]
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

;; This procedure sets all traffic lights to yellow
to set-signal-yellow  ;; intersection (patch) procedure
  if dirx = "right" and diry = "down"
  [
    ask patch-at -1 0 [ set pcolor yellow + 1]
    ask patch-at 0 1 [ set pcolor yellow + 1 ]
  ]
  if dirx = "right" and diry = "up"
  [
    ask patch-at -1 0 [ set pcolor yellow + 1]
    ask patch-at 0 -1 [ set pcolor yellow + 1 ]
  ]
  if dirx = "left" and diry = "down"
  [
    ask patch-at 1 0 [ set pcolor yellow + 1]
    ask patch-at 0 1 [ set pcolor yellow + 1 ]
  ]
  if dirx = "left" and diry = "up"
  [
    ask patch-at 1 0 [ set pcolor yellow + 1]
    ask patch-at 0 -1 [ set pcolor yellow + 1]
  ]
end

;; set the turtles' speed based on whether they are at a red traffic light or the speed of the
;; turtle (if any) on the patch in front of them
to set-car-speed  ;; turtle procedure
  ifelse [pcolor] of patch-here = 15
  [ set speed 0 ]
  [ set-speed]
end

;; set the speed variable of the car to an appropriate value (not exceeding the
;; speed limit) based on whether there are cars on the patch in front of thecar
to set-speed  ;; turtle procedure
              ;; get the turtles on the patch in front of the turtle
  let cars-ahead other cars-on patch-ahead 1

  ;; if there are turtles in front of the turtle, slow down
  ;; otherwise, speed up
  ifelse any? cars-ahead
  [
    set speed [speed] of one-of cars-ahead
    slow-down
  ]
  [if [pcolor] of patch-here != red [speed-up]]

  ;;check for yellow lights
  if [pcolor] of patch-ahead 1 = yellow + 1 [
    slow-down
  ]
  ;; only drive on intersections if road afterwards is free
  if member? patch-ahead 1 intersections and is-list? nav-pathtofollow and length nav-pathtofollow  > 1[
    let node-after item 1 nav-pathtofollow
    let x [xcor] of node-after
    let y [ycor] of node-after
    let patch-after patch x y
    if any? other cars-on patch-after or any? (cars-ahead)[ ;with [ direction-turtle != [direction-turtle] of myself ])[
      set speed 0
    ]
  ]
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

;; set the color of the turtle to a different color based on whether the car is paying for parking
to set-car-color  ;; turtle procedure
  ifelse paid? != false
  [ set color grey]
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

end

to record-globals ;; keep track of all global reporter variables
  set mean-income mean [income] of cars
  set median-income median [income] of cars
  set n-cars count cars / num-cars
  set mean-wait-time mean [wait-time] of cars
  if count cars with [not parked?] > 0 [set mean-speed (mean [speed] of cars with [not parked?]) / speed-limit]

  set yellow-lot-current-fee mean [fee] of yellow-lot
  set green-lot-current-fee mean [fee] of green-lot
  set teal-lot-current-fee mean [fee] of teal-lot
  set blue-lot-current-fee mean [fee] of blue-lot

  set global-occupancy count cars-on lots / count lots

  set yellow-lot-current-occup count cars-on yellow-lot / count yellow-lot
  set green-lot-current-occup count cars-on green-lot / count green-lot
  set teal-lot-current-occup count cars-on teal-lot / count teal-lot
  set blue-lot-current-occup count cars-on blue-lot / count blue-lot
  if num-garages > 0 [set garages-current-occup count cars-on garages / count garages]
  set normalized-share-poor ((count cars with [income-grade = 0] / count cars)  / initial-poor)
  if normalized-share-poor > 1 [set normalized-share-poor 1]

  if count cars with [not parked?] > 0 [set share-cruising count cars with [park <= parking-cars-percentage and not parked?] / count cars with [not parked?]]
  ;set income-entropy compute-income-entropy
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
  ;; check whether parking spot on left or right is available
  if (not parked? and (ticks > 0)) [
    (foreach [0 0 1 -1] [1 -1 0 0][ [a b] ->
      if [gateway?] of patch-at a b = true [
        park-in-garage patch-at a b
        set distance-parking-target distance nav-goal ;; update distance to goal
        stop
      ]
      if ((member? (patch-at a b) lots) and (not any? cars-at a b))[
        let parking-fee [fee] of patch-at a b  ;; compute fee
                                               ;; check for parking offenders
        let fine-probability compute-fine-prob park-time
        ;; check if parking offender or WTP larger than fee
        ifelse (parking-offender? and (wtp >= ([fee] of patch-at a b * fines-multiplier)* fine-probability ))[
          set paid? false
          set expected-fine ([fee] of patch-at a b * fines-multiplier)* fine-probability
          set city-loss city-loss + parking-fee
        ]
        [
          ifelse (wtp >= parking-fee)
          [
            set paid? true
            set city-income city-income + parking-fee
            set price-paid parking-fee
          ]
          ;; keep track of checked lots
          [
            if not member? patch-at a b lots-checked
            [
              let lot-identifier [lot-id] of patch-at a b ;; value of lot-variable for current lot
              let current-lot lots with [lot-id = lot-identifier]
              set lots-checked (patch-set lots-checked current-lot)
              update-wtp
            ]
            stop
          ]
        ]
        set-car-color
        move-to patch-at a b
        set parked? true
        set looks-for-parking? false
        set nav-prklist []
        set nav-hastarget? false
        set fee-income-share (parking-fee / (income / 12)) ;; share of monthly income
        ask patch-at a b [set car? true]
        set lots-checked no-patches
        set distance-parking-target distance nav-goal ;; update distance to goal
        stop
      ]
      ]
    )
  ]
end

to park-in-garage [gateway] ;; procedure to park in garage
  let current-garage garages with [lot-id = [lot-id] of gateway]
  if (count cars-on current-garage / count current-garage) < 1[
    let parking-fee (mean [fee] of current-garage)  ;; compute fee
    ifelse (wtp >= parking-fee)
    [
      let space one-of current-garage with [not any? cars-on self]
      move-to space
      ask space [set car? true]
      set paid? true
      set price-paid parking-fee
      ;;set city-income city-income + parking-fee
      set parked? true
      set looks-for-parking? false
      set nav-prklist []
      set nav-hastarget? false
      set fee-income-share (parking-fee / (income / 12))
      set lots-checked no-patches
      stop
    ]
    [
      if not member? gateway lots-checked
      [
        let lot-identifier [lot-id] of gateway ;; value of lot-variable for current garage
        let current-lot lots with [lot-id = lot-identifier]
        set lots-checked (patch-set lots-checked current-lot)
        update-wtp
      ]
      stop
    ]
  ]
end

to unpark-car ;; turtle procedure
  ifelse (time-parked < park-time)[
    set time-parked time-parked + 1
  ]
  [
    if num-garages > 0 and member? patch-here garages [
      unpark-from-garage
      stop
    ]
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
        ;set park 100
        set time-parked 0
        set-car-color
        set reinitialize? true
        ask patch-here[
          set car? false
        ]
        stop
      ]
    ])
  ]
end


to unpark-from-garage ;;
  let space patch-here
  let gateway gateways with [lot-id = [lot-id] of space]
  let road []
  ask gateway [set road one-of neighbors4 with [member? self roads]] ;; must use one-of to interpret as single agent
  if not any? cars-on road [
    set direction-turtle [direction] of road
    move-to road
    set parked? false
    ;set park 100
    set time-parked 0
    set-car-color
    set reinitialize? true
    ask space[
      set car? false
    ]
    stop
  ]
end

to document-turtle;;
  let park-bool False
  if [park] of self <= parking-cars-percentage [set park-bool True]
  file-print  csv:to-row [(list who income income-grade wtp parking-offender? distance-parking-target price-paid search-time park-bool die? reinitialize?)] of self
end


;; compute utility
to compute-outcome
  ;; consider only cars trying to park
  let parking-cars cars with [park <= parking-cars-percentage ]
  if count parking-cars > 0 [
    let access-factor 20 / 1800 ;; 20$ per hour
    let egress-factor 50 / (60 * 60) ;; 50$ per hour, translated to seconds
    ask parking-cars [
      set outcome wtp
      set outcome outcome - access-factor * search-time
      if price-paid != -99 [set outcome outcome - price-paid] ;; check whether any price was paid
      if distance-parking-target != -99 [set outcome outcome - distance-parking-target * egress-factor * (5 / 1.4)] ;; 5 patches  = 1 meter, 1.4 meter per second
      if expected-fine != -99 [set outcome outcome - expected-fine]
    ]
    let min-outcome min [outcome] of cars with [outcome != -99]
    let max-outcome max [outcome] of cars with [outcome != -99]
    let outcome-range max-outcome - min-outcome
    ask cars with [outcome != -99] [
      set outcome (outcome - min-outcome) / outcome-range
    ]
  ]
end


to-report get-outcomes [group]
  ifelse group = "all" [
    ifelse count cars with [outcome != -99] > 0 [
      report [outcome] of cars with [outcome != -99]
    ]
    [
      report 0
    ]
  ]
  [
    ifelse count cars with [outcome != -99 and income-grade = group] > 0 [
      report [outcome] of cars with [outcome != -99 and income-grade = group]
    ]
    [
      report 0
    ]
  ]
end

to-report compute-gini
  let sorted-outcome sort [outcome] of cars with [outcome != -99]
  let height 0
  let area 0
  foreach sorted-outcome [oc ->
    set height height + oc
    set area area + (height - oc / 2)
  ]
  let fair-area height * (length sorted-outcome / 2 )
  report (fair-area - area) / fair-area
end


;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Environment procedures ;;
;;;;;;;;;;;;;;;;;;;;;;;;;;;;

to update-baseline-fees;;
  if (ticks mod (temporal-resolution / 2) = 0 and ticks > 0) [ ;; update fees every half hour
    let occupancy 0
    foreach lot-colors [ lot-color ->
      let current-lot lots with [pcolor = lot-color]
      if any? cars-on current-lot [
        set occupancy (count cars-on current-lot / count current-lot)
      ]


      (ifelse
        occupancy >= 0.9 [
          change-fee current-lot 0.25
        ]
        occupancy < 0.75 and occupancy >= 0.3 [
          change-fee current-lot -0.25
        ]
        occupancy < 0.3 and mean [fee] of current-lot >= 1 [
          change-fee current-lot -0.5
        ]
      )
    ]
  ]
end

;; for changing prices during Reinforcement Learning
to change-fee [lot fee-change]
  let new-fee (mean [fee] of lot) + fee-change
  ;; 0 is the minimum fee
  if new-fee < 0 [stop]
  ask lot [set fee fee + fee-change]
end

;; for free price setting of RL agent
to change-fee-free [lot new-fee]
  ;; 0 is the minimum fee
  if new-fee < 0 [stop]
  ask lot [set fee new-fee]
end

to update-wtp ;;
              ;; cars that did not find a place do not respawn
  if empty? nav-prklist [
    set reinitialize? false
    set die? true
    (ifelse
      income-grade = 0 [
        set vanished-cars-poor vanished-cars-poor + 1
      ]
      income-grade = 1 [
        set vanished-cars-middle vanished-cars-middle + 1
      ]
      income-grade = 2 [
        set vanished-cars-rich vanished-cars-rich + 1
      ]
    )
  ]

  if wtp-increased <= 5
    [
      set wtp wtp + wtp * .05
      set wtp-increased wtp-increased + 1
  ]
end

to recreate-cars;;
  create-cars cars-to-create
  [
    set reinitialize? true
    setup-cars
    set-car-color
    record-data
    if park > parking-cars-percentage [
      set nav-prklist []
      set reinitialize? true
    ]
  ]
  set cars-to-create 0
end

;; keep distribution of incomes approx. constant
to keep-distro [income-class]
  (ifelse
    income-class = 0 [
      set poor-to-create poor-to-create + 1
    ]
    income-class = 1 [
      set middle-to-create middle-to-create + 1
    ]
    income-class = 2 [
      set high-to-create high-to-create + 1
    ]
  )
end

to update-search-time
  if not parked?
  [set search-time search-time + 1]

  ;; output-print search-time
end

;; randomly check for parking offenders every hour
to control-lots
  if ticks > 0 and (ticks mod (temporal-resolution / controls-per-hour) = 0) [
    let switch random 4
    (ifelse
      switch = 0 [
        let potential-offenders cars-on yellow-lot
        let fines (count potential-offenders with [not paid?]) *  fines-multiplier * mean [fee] of yellow-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
      ]
      switch = 1 [
        let potential-offenders cars-on teal-lot
        let fines (count potential-offenders with [not paid?]) * fines-multiplier * mean [fee] of teal-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
      ]
      switch = 2 [
        let potential-offenders cars-on green-lot
        let fines (count potential-offenders with [not paid?]) * fines-multiplier * mean [fee] of green-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
      ]
      switch = 3[
        let potential-offenders cars-on blue-lot
        let fines (count potential-offenders with [not paid?]) * fines-multiplier * mean [fee] of blue-lot
        set city-income city-income + fines
        set total-fines total-fines + fines
    ])
  ]
end

to-report compute-fine-prob [parking-time] ;;computes probabilty to get caught for parking-offenders
  let n-controls round(parking-time / (temporal-resolution / controls-per-hour))
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

;; draw parking duration following a gamma distribution
to-report draw-park-duration
  let minute temporal-resolution / 60
  let shift temporal-resolution / 3 ;; have minimum of 20 minutes
  set shift 0
  let mu 227.2 * minute
  let sigma (180 * minute) ^ 2
  report random-gamma ((mu ^ 2) / sigma) (1 / (sigma / mu)) + shift
end

;; global reporter: draws a random income, based on the distribution provided by the user
to-report draw-income
  let sigma  sqrt (2 * ln (pop-mean-income / pop-median-income))
  let mu     (ln pop-median-income)
  report exp random-normal mu sigma
end

to-report draw-sampled-income ;;global reporter, draws a random income based on the distribution in the sample
                              ;; use absolute value for cases in which median becomes larger than mean (not in use currently)
  let sigma  sqrt abs (2 * ln (mean-income / median-income))
  let mu     (ln median-income)
  report exp random-normal mu sigma
end


to-report find-income-grade ;;check borders
  let sigma sqrt (2 * ln (pop-mean-income / pop-median-income))
  if income > (pop-mean-income + pop-mean-income * sigma * 1)
  [
    report 2
  ]
  if income > (pop-mean-income - pop-mean-income * sigma * 1) and income <= (pop-mean-income + pop-mean-income * sigma * 1)
  [
    report 1
  ]
  if income <= (pop-mean-income - pop-mean-income * sigma * 1)
  [
    report 0
  ]
end

to-report draw-wtp ;;
  let mu 0
  let sigma 0
  (ifelse
    income-grade = 0 [
      set mu 2.5
      set sigma mu * 0.25
    ]
    income-grade = 1 [
      set mu 4.5
      set sigma mu * 0.30
    ]
    income-grade = 2 [
      set mu 8
      set sigma mu * 0.45
    ]
  )
  ;;report abs (random-normal mu sigma)
  report random-gamma ((mu ^ 2) / sigma) (1 / (sigma / mu))
end

to-report compute-income-entropy
  let prop-poor (count cars with [income-grade = 0] / count cars)
  let prop-middle (count cars with [income-grade = 1] / count cars)
  let prop-rich (count cars with [income-grade = 2] / count cars)
  let entropy 0
  foreach (list prop-poor prop-middle prop-rich) [ class ->
    if class > 0 [
      set entropy entropy + class * ln class
    ]
  ]

  let max-entropy -3 * (1 / 3 * ln (1 / 3))
  report (- entropy / max-entropy)
end

; Copyright 2003 Uri Wilensky.
; See Info tab for full copyright and license.
@#$#@#$#@
GRAPHICS-WINDOW
362
80
1520
1807
-1
-1
14.2
1
9
1
1
1
0
1
1
1
-40
40
-60
60
1
1
1
ticks
60.0

PLOT
2948
797
3385
1180
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
"Waittime" 1.0 0 -16777216 true "" "plot mean-wait-time"
"Average speed" 1.0 0 -2674135 true "" "plot mean-speed"

SLIDER
18
183
299
216
num-cars
num-cars
10
1000
550.0
5
1
NIL
HORIZONTAL

PLOT
1557
80
1962
416
Share of Cars per Income Class
Time
%
0.0
21600.0
0.0
100.0
true
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "plot ((count cars with [income-grade = 2] / count cars) * 100)"
"Middle Income" 1.0 0 -13791810 true "" "plot ((count cars with [income-grade = 1] / count cars) * 100)"
"Low Income" 1.0 0 -2674135 true "" "ifelse count cars with [income-grade = 0] != 0 [plot ((count cars with [income-grade = 0] / count cars) * 100)][plot 0] "
"Share of intially spawned cars" 1.0 0 -7500403 true "" "plot (n-cars) * 100"
"Entropy" 1.0 0 -955883 true "" "plot income-entropy * 100"

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
5
763
199
796
blue-lot-fee
blue-lot-fee
0
20
2.0
0.5
1
€ / hour
HORIZONTAL

SLIDER
4
603
190
636
yellow-lot-fee
yellow-lot-fee
0
20
2.0
0.5
1
€ / hour
HORIZONTAL

SLIDER
7
709
192
742
teal-lot-fee
teal-lot-fee
0
20
2.0
0.5
1
€ / hour
HORIZONTAL

SLIDER
9
655
194
688
green-lot-fee
green-lot-fee
0
20
2.0
0.5
1
€ / hour
HORIZONTAL

PLOT
1556
793
1967
1168
Utilized Capacity at Different Lots
Time
Utilized Capacity in %
0.0
21.0
0.0
100.0
true
true
"set-plot-background-color grey - 2\n" ""
PENS
"Blue Lot" 1.0 0 -13740902 true "" "plot blue-lot-current-occup * 100"
"Yellow Lot" 1.0 0 -855445 true "" "plot yellow-lot-current-occup * 100"
"Green Lot" 1.0 0 -8732573 true "" "plot green-lot-current-occup * 100"
"Teal  Lot" 1.0 0 -14520940 true "" "plot teal-lot-current-occup * 100"
"Garages" 1.0 0 -15520724 true "" "if num-garages > 0 [plot garages-current-occup * 100]"
"Overall Occupancy" 1.0 0 -7500403 true "" "plot global-occupancy * 100"

MONITOR
203
1125
338
1170
Mean Income in Model
mean [income] of cars
2
1
11

SLIDER
6
1126
187
1159
pop-median-income
pop-median-income
10000
40000
23515.0
1
1
€
HORIZONTAL

SLIDER
6
1080
187
1113
pop-mean-income
pop-mean-income
0
50000
26105.0
1
1
€
HORIZONTAL

PLOT
1987
793
2451
1176
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
4
1173
186
1206
wtp-income-share
wtp-income-share
0
0.01
0.003
0.001
1
NIL
HORIZONTAL

TEXTBOX
47
554
151
576
Initial Fees
15
0.0
1

MONITOR
244
760
325
805
blue-lot-fee
mean [fee] of blue-lot
17
1
11

MONITOR
242
599
321
644
yellow-lot-fee
mean [fee] of yellow-lot
17
1
11

MONITOR
244
705
326
750
teal-lot-fee
mean [fee] of teal-lot
17
1
11

MONITOR
242
653
329
698
green-lot-fee
mean [fee] of green-lot
17
1
11

TEXTBOX
239
556
324
575
Current Fees
15
0.0
1

PLOT
2463
436
2893
732
Descriptive Income Statistics
Time
Euro
0.0
7200.0
0.0
32000.0
true
true
"" ""
PENS
"Mean" 1.0 0 -16777216 true "" "plot mean-income"
"Median" 1.0 0 -2674135 true "" "plot median-income"
"Standard Deviation" 1.0 0 -13791810 true "" "plot standard-deviation [income] of cars "

PLOT
1556
430
1964
729
Average Search Time per Income Class
Time
Time
0.0
7200.0
0.0
1500.0
true
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "ifelse count cars with [income-grade = 2] != 0 [plot mean [search-time] of cars with [income-grade = 2]][plot 0] "
"Middle Income" 1.0 0 -13791810 true "" "plot mean [search-time] of cars with [income-grade = 1]"
"Low Income" 1.0 0 -2674135 true "" "ifelse count cars with [income-grade = 0] != 0 [plot mean [search-time] of cars with [income-grade = 0]][plot 0] "

TEXTBOX
89
1036
280
1086
Income Distribution
20
0.0
1

TEXTBOX
22
526
172
551
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
187
265
316
298
hide-nodes
hide-nodes
0
1
-1000

SLIDER
22
385
268
418
lot-distribution-percentage
lot-distribution-percentage
0
1
0.55
0.05
1
NIL
HORIZONTAL

MONITOR
203
1075
338
1120
Min Income in Model
min [income] of cars
2
1
11

MONITOR
203
1179
337
1224
Max Income in Model
Max [income] of cars
2
1
11

SWITCH
189
306
321
339
show-goals
show-goals
1
1
-1000

PLOT
1975
81
2447
418
Share of parked Cars per Income Class
Time
%
0.0
7200.0
0.0
100.0
true
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "ifelse count cars with [parked? = true and park <= parking-cars-percentage and income-grade = 2] != 0 [plot (count cars with [parked? = true and income-grade = 2] / count cars with [park <= parking-cars-percentage and income-grade = 2]) * 100][plot 0]"
"Middle Income" 1.0 0 -13791810 true "" "ifelse count cars with [parked? = true and park <= parking-cars-percentage and income-grade = 1] != 0 [plot (count cars with [parked? = true and income-grade = 1] / count cars with [park <= parking-cars-percentage and income-grade = 1]) * 100][plot 0]"
"Low Income" 1.0 0 -2674135 true "" "ifelse count cars with [parked? = true and park <= parking-cars-percentage and income-grade = 0] != 0 [plot (count cars with [parked? = true and income-grade = 0] / count cars with [park <= parking-cars-percentage and income-grade = 0]) * 100][ plot 0]"

SLIDER
40
895
235
928
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
33
852
299
888
How high should the fines be in terms of the original hourly fee?
13
0.0
1

PLOT
1977
431
2451
728
Fee as Share of Monthly Income per Income Class
Time
%
0.0
7200.0
0.0
2.0
true
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "if count cars with [parked? = true and income-grade = 2] != 0 [plot mean [fee-income-share] of cars with [parked? = true and income-grade = 2] * 100]"
"Middle Income" 1.0 0 -13791810 true "" "plot mean [fee-income-share] of cars with [parked? = true and income-grade = 1] * 100"
"Low Income" 1.0 0 -2674135 true "" "if count cars with [parked? = true and income-grade = 0] != 0 [plot mean [fee-income-share] of cars with [parked? = true and income-grade = 0] * 100]"

MONITOR
1860
159
1960
204
Number of Cars
count cars
17
1
11

TEXTBOX
1898
37
2048
62
Social Indicators
20
0.0
1

PLOT
2461
81
2893
421
Share of Income Class on Yellow Lot
Time
%
0.0
7200.0
0.0
100.0
true
true
"" ""
PENS
"High Income" 1.0 0 -16777216 true "" "ifelse count cars-on yellow-lot != 0 [plot (count cars with [([pcolor] of patch-here = [255.0 254.997195 102.02397]) and income-grade = 2] / count cars-on yellow-lot) * 100] [plot 0]"
"Middle Income" 1.0 0 -13791810 true "" "ifelse count cars-on yellow-lot != 0 [plot (count cars with [([pcolor] of patch-here = [255.0 254.997195 102.02397]) and income-grade = 1] / count cars-on yellow-lot) * 100] [plot 0]"
"Low Income" 1.0 0 -2674135 true "" "ifelse count cars-on yellow-lot != 0 [plot (count cars with [([pcolor] of patch-here = [255.0 254.997195 102.02397]) and income-grade = 0] / count cars-on yellow-lot) * 100][plot 0]"

TEXTBOX
2048
759
2352
803
Traffic and Financial Indicators
20
0.0
1

TEXTBOX
34
941
274
989
How often every hour should one of the lots be controlled?
13
0.0
1

SLIDER
35
987
244
1020
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
2477
793
2895
1179
Dynamic Fee of Different Lots
Time
Euro
0.0
7200.0
0.0
5.0
true
true
"set-plot-background-color grey - 2" ""
PENS
"Yellow Lot" 1.0 0 -855445 true "" "plot yellow-lot-current-fee"
"Teal Lot" 1.0 0 -14520940 true "" "plot teal-lot-current-fee"
"Green Lot" 1.0 0 -8732573 true "" "plot green-lot-current-fee"
"Blue Lot" 1.0 0 -13740902 true "" "plot blue-lot-current-fee"

SWITCH
186
225
334
258
demo-mode
demo-mode
1
1
-1000

SLIDER
23
431
243
464
target-start-occupancy
target-start-occupancy
0
1
0.5
0.05
1
NIL
HORIZONTAL

SLIDER
66
1299
238
1332
temporal-resolution
temporal-resolution
0
3600
1800.0
100
1
NIL
HORIZONTAL

TEXTBOX
86
1253
236
1281
How many ticks should be considered equal to one hour?
11
0.0
1

SLIDER
23
477
195
510
num-garages
num-garages
0
5
2.0
1
1
NIL
HORIZONTAL

SWITCH
66
805
286
838
dynamic-pricing-baseline
dynamic-pricing-baseline
0
1
-1000

SLIDER
22
516
224
549
parking-cars-percentage
parking-cars-percentage
0
100
90.0
1
1
%
HORIZONTAL

PLOT
2918
96
3347
396
Vanished Vars per Income Class
Time
Cars
0.0
10.0
0.0
10.0
true
true
"" ""
PENS
"Low Income" 1.0 0 -2674135 true "" "plot vanished-cars-poor"
"Middle Income" 1.0 0 -13345367 true "" "plot vanished-cars-middle"
"High Income" 1.0 0 -16777216 true "" "plot vanished-cars-rich"

INPUTBOX
16
1371
273
1431
output-turtle-file-path
test.csv
1
0
String

SWITCH
187
342
337
375
document-turtles
document-turtles
1
1
-1000

@#$#@#$#@
# WHAT IS IT?

This is a model of traffic moving in a city grid. A portion of the agents tries to park on the curbside or the parking garages. The model is based on the traffic grid model by (Wilensky, 2003) and the seminar paper by (Aziz et al., 2020).



# Environment

The model’s environment is defined by a grid layout of roads and blocks. Located at the curbside, the yellow, green, teal, and blue patches designate parking spaces that are randomly scattered across the grid. Stripes of parking places situated opposite to one another are grouped. The coloring, indicating the different CPZs (Controlled Parking Zones) in the model, is then assigned depending on the distance of the groups to the center of the map, with the brightness of the colors decreasing the larger this distance grows. Due to their centrality, the green and, mainly, the yellow CPZ can be interpreted as most closely resembling the Central Business District (CBD) of the simulated city center. Beyond that, this model also introduces parking garages to account for off-street parking represented by the large blocks of black patches scattered across the map.

# Agents and Attributes

The central agents of our model are cars moving across the grid. In particular, 90% of all vehicles look for parking, and the remainder traverses the grid. For each car cruising for parking, a random parking duration is drawn from a gamma distribution, which was adopted from (Jakob & Menendez, 2021).

### Income

For every car, an income is randomly drawn from a log-normal distribution. Related work shows that the income of up to 99% of the population can be approximated with a two-parameter log-normal distribution (Clementi & Gallegati, 2005).


We calibrated the two parameters (the population mean and the population median) following the income distribution of the country our model city is located in. Based on the standard deviation, cars are divided into three income classes: Incomes within one standard deviation of the mean (68.2% of the population) are assigned the “middle-income” class. Deviations above or below this mark are called “high-” or “low-income”, (both 15.8% of the population) respectively.

### Willingness to Pay (WTP)

This variable captures the amount of money a driver is willing to pay for parking per
hour. Although income is a significant determinant of WTP, studies stress the importance of behavioral factors such as perceived comfort and security. To account for this individual variance, we randomly draw the WTP for each driver from a gamma distribution dependent on their income class.

Due to a lack of empirical evidence, the parameters of the distribution were manually calibrated to preserve the correlation between income and WTP and to ensure the functioning of the underlying parking routines in the model, i.e. to avoid excluding low-income drivers completely from parking: While for low-income drivers a mean of 2.5€ per hour was selected, the means for middle- and high-income cars amount to 4.5€ and 8€ per hour, respectively. Concerning the variance, for every income level, it was calibrated to correspond to the respective variance of the class-specific income distribution relative to its mean, mimicking the shapes of the individual intra-class income distributions. Specifying whether they are willing to park on a parking place without paying, the agents own the attribute parking-offender?.


# Behavioral Rules

### Navigation

All cars navigate the grid with previously assigned goals. For traversing cars, this goal is one of the exit points of the street network. For cars seeking to park, destinations are assigned with probabilities inversely proportional to their distance to the center of the grid, accounting for the higher popularity of the CBD. After target assignment, cars curate a list of the closest parking opportunities and elect the shortest route to the first one according to the NetLogo network extension.4 Upon arrival, cars attempt to park in the road of their assigned target. If no spot is available (or if spots are too expensive), cars move to the next list item. Similar to (Shoup, 2011), garages are only considered if there is no curbside parking at a cheaper cost since curbside parking is generally considered the more attractive option.

### Parking

Once a car has entered the street with its parking location of choice, it requests the fee of the closest available CPZ. If the fee is within the WTP, the car parks and the fee is added to the municipality revenues; if the fee exceeds the WTP, the driver will resume searching. We assume that WTP increases proportionally to the time spent cruising for parking. If a car belongs to the parking offenders, it will calculate the probability of getting caught. For this calculation, we assume rational actors with complete knowledge of the environment (i.e., the number of controls per hour and the fine as a multiple of the parking price are known a priori to offenders). Upon completion of their parking time, cars leave the CPZ and navigate towards the edge of the grid, where they are replaced with newly set up cars. In contrast, cars unable to find parking are not replaced once they leave the map. This preserves the change to the social distribution in the model that this behavior introduces.

# Sources

Aziz, M., Daube, J., Exner, P., Gutmann, J., Klenk, J., & Vyas, A. (2020). An Agent-Based Model for Simulating the Effect of Parking Prices [Seminar Report]. University of Mannheim.

Clementi, F., & Gallegati, M. (2005). Pareto’s Law of Income Distribution: Evidence for Germany, the United Kingdom, and the United States. In A. Chatterjee, S. Yarlagadda, & B. K. Chakrabarti (Eds.), Econophysics of Wealth Distributions (pp. 3–14). Springer Milan. https://doi.org/10.1007/88-470-0389-X_1


Jakob, M., & Menendez, M. (2021). Parking Pricing Vs. Congestion Pricing: A Macroscopic Analysis of Their Impact on Traffic. Transportmetrica A: Transport Science, 17(4), 462–491. https://doi.org/10.1080/23249935.2020.1797924

Shoup, D. (2011). The High Cost of Free Parking (Updated). Planners Press, American Planning Association.

Wilensky, U. (2003). Netlogo Traffic Grid Model. Center for Connected Learning and Computer-Based Modeling, Northwestern University. http://ccl.northwestern.edu/netlogo/models/TrafficGrid



<!-- 2022 -->
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

car side
false
0
Polygon -7500403 true true 19 147 11 125 16 105 63 105 99 79 155 79 180 105 243 111 266 129 253 149
Circle -16777216 true false 43 123 42
Circle -16777216 true false 194 124 42
Polygon -16777216 true false 101 87 73 108 171 108 151 87
Line -8630108 false 121 82 120 108
Polygon -1 true false 242 121 248 128 266 129 247 115
Rectangle -16777216 true false 12 131 28 143

car top
true
0
Polygon -7500403 true true 151 8 119 10 98 25 86 48 82 225 90 270 105 289 150 294 195 291 210 270 219 225 214 47 201 24 181 11
Polygon -16777216 true false 210 195 195 210 195 135 210 105
Polygon -16777216 true false 105 255 120 270 180 270 195 255 195 225 105 225
Polygon -16777216 true false 90 195 105 210 105 135 90 105
Polygon -1 true false 205 29 180 30 181 11
Line -7500403 false 210 165 195 165
Line -7500403 false 90 165 105 165
Polygon -16777216 true false 121 135 180 134 204 97 182 89 153 85 120 89 98 97
Line -16777216 false 210 90 195 30
Line -16777216 false 90 90 105 30
Polygon -1 true false 95 29 120 30 119 11

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
NetLogo 6.2.2
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
<experiments>
  <experiment name="experiment" repetitions="1" runMetricsEveryStep="true">
    <setup>setup</setup>
    <go>go</go>
    <timeLimit steps="21600"/>
    <metric>count turtles</metric>
    <enumeratedValueSet variable="hide-nodes">
      <value value="true"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="demo-mode">
      <value value="false"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="target-start-occupancy">
      <value value="0.5"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="blue-lot-fee">
      <value value="2"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="green-lot-fee">
      <value value="2"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="show-goals">
      <value value="false"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="pop-median-income">
      <value value="22713"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="yellow-lot-fee">
      <value value="2"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="controls-per-hour">
      <value value="2"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="fines-multiplier">
      <value value="5"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="ticks-per-cycle">
      <value value="20"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="num-garages">
      <value value="0"/>
      <value value="1"/>
      <value value="2"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="temporal-resolution">
      <value value="1800"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="lot-distribution-percentage">
      <value value="0.8"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="wtp-income-share">
      <value value="0.005"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="pop-mean-income">
      <value value="25882"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="num-cars">
      <value value="490"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="dynamic-pricing-baseline">
      <value value="true"/>
    </enumeratedValueSet>
    <enumeratedValueSet variable="orange-lot-fee">
      <value value="2"/>
    </enumeratedValueSet>
  </experiment>
</experiments>
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
