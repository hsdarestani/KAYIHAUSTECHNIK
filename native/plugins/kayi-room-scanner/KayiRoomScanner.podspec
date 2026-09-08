Pod::Spec.new do |s|
  s.name = 'KayiRoomScanner'
  s.version = '1.0.0'
  s.summary = 'Native RoomPlan scanner for KAYI Haustechnik'
  s.license = { :type => 'Proprietary' }
  s.homepage = 'https://kayi.smarbiz.sbs'
  s.author = { 'KAYI' => 'support@kayi.smarbiz.sbs' }
  s.source = { :path => '.' }
  s.source_files = 'ios/Sources/KayiRoomScannerPlugin/**/*.{swift}'
  s.ios.deployment_target = '16.0'
  s.swift_version = '5.9'
  s.dependency 'Capacitor'
  s.frameworks = 'UIKit', 'RoomPlan'
end
